from pathlib import Path
from typing import Dict, Generator
import logging

from uar.core.registry import register_skill
from uar.core.exceptions import PathSecurityError
from uar.core.validation import validate_path_security

logger = logging.getLogger(__name__)

ALLOWED_ROOT = Path('.').resolve()
ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".ts", ".tsx", ".json", ".js", ".jsx", ".yaml", ".yml"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES = 1000
MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB total limit to prevent memory exhaustion


def _read_file_safely(file_path: Path, allowed_root: Path) -> Dict[str, str]:
    """Read a single file with proper resource management and security checks.
    
    Uses context manager to ensure file handle is closed even on errors.
    """
    try:
        # Validate security before reading
        validate_path_security(file_path, allowed_root)
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return {
                "path": str(file_path.relative_to(allowed_root)),
                "text": "",
                "size": 0,
                "error": f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})"
            }
        
        # Use context manager for proper file handle cleanup
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            content = f.read()
            
        return {
            "path": str(file_path.relative_to(allowed_root)),
            "text": content,
            "size": len(content)
        }
        
    except UnicodeDecodeError:
        return {
            "path": str(file_path.relative_to(allowed_root)) if file_path.is_relative_to(allowed_root) else str(file_path),
            "text": "",
            "size": 0,
            "error": "File encoding error (not valid UTF-8)"
        }
    except PermissionError:
        return {
            "path": str(file_path.relative_to(allowed_root)) if file_path.is_relative_to(allowed_root) else str(file_path),
            "text": "",
            "size": 0,
            "error": "Permission denied"
        }
    except Exception as e:
        return {
            "path": str(file_path.relative_to(allowed_root)) if file_path.is_relative_to(allowed_root) else str(file_path),
            "text": "",
            "size": 0,
            "error": f"Read error: {str(e)}"
        }


def _yield_documents(path: Path, allowed_root: Path) -> Generator[Dict[str, str], None, None]:
    """Generator to yield documents one at a time to avoid loading all into memory."""
    file_count = 0
    total_size = 0
    
    if path.is_file():
        if path.suffix.lower() in ALLOWED_EXTENSIONS:
            doc = _read_file_safely(path, allowed_root)
            if "error" not in doc or doc["error"] == "":
                yield doc
        else:
            yield {
                "path": str(path.relative_to(allowed_root)) if path.is_relative_to(allowed_root) else str(path),
                "text": "",
                "size": 0,
                "error": f"Unsupported file type: {path.suffix}"
            }
    elif path.is_dir():
        # Use scandir for better memory efficiency than rglob
        for entry in sorted(path.rglob("*")):
            if file_count >= MAX_FILES:
                yield {
                    "path": "LIMIT_EXCEEDED", 
                    "text": f"Stopped at {MAX_FILES} files",
                    "size": 0,
                    "warning": "Maximum file count reached"
                }
                return
            
            if total_size >= MAX_TOTAL_SIZE:
                yield {
                    "path": "SIZE_LIMIT_EXCEEDED",
                    "text": f"Stopped at {total_size} bytes",
                    "size": 0,
                    "warning": "Maximum total size reached"
                }
                return
                
            if entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    # Quick size check before reading
                    entry_size = entry.stat().st_size
                    if entry_size > MAX_FILE_SIZE:
                        yield {
                            "path": str(entry.relative_to(allowed_root)) if entry.is_relative_to(allowed_root) else str(entry),
                            "text": "",
                            "size": 0,
                            "error": f"File too large: {entry_size} bytes"
                        }
                        file_count += 1
                        continue
                    
                    doc = _read_file_safely(entry, allowed_root)
                    file_count += 1
                    
                    if "error" not in doc or doc["error"] == "":
                        total_size += doc.get("size", 0)
                    
                    yield doc
                    
                except OSError as e:
                    # Handle race conditions where file is deleted between check and read
                    logger.warning(f"File access error for {entry}: {e}")
                    continue
    else:
        yield {
            "path": str(path),
            "text": "",
            "size": 0,
            "error": f"Input path not found: {path}"
        }


@register_skill("doc_ingest")
def doc_ingest(ctx):
    """Ingest documents from a specified path with security validation.
    
    Features:
    - Proper resource management with context managers
    - Memory-efficient streaming via generators
    - Total size limits to prevent memory exhaustion
    - Comprehensive error handling for individual files
    - Security validation at every access point
    """
    input_path = ctx.goal.metadata.get("input_path")
    if not input_path:
        return {"documents": [], "warning": "No input_path provided"}

    try:
        path = Path(input_path).resolve()
        
        # Validate path security before any access
        validate_path_security(path, ALLOWED_ROOT)
        
        # Use generator and convert to list with size limits enforced
        documents = []
        total_size = 0
        doc_count = 0
        
        for doc in _yield_documents(path, ALLOWED_ROOT):
            documents.append(doc)
            doc_count += 1
            
            # Track size only for successfully read documents
            if "error" not in doc or doc["error"] == "":
                total_size += doc.get("size", 0)
            
            # Early termination if limits exceeded
            if doc_count >= MAX_FILES or total_size >= MAX_TOTAL_SIZE:
                break
        
        return {
            "documents": documents,
            "document_count": len([d for d in documents if "error" not in d or d.get("error") == ""]),
            "paths": [doc["path"] for doc in documents if "error" not in doc or doc.get("error") == ""],
            "total_size": total_size,
            "errors": [doc["error"] for doc in documents if "error" in doc and doc["error"]],
        }
        
    except PathSecurityError as e:
        logger.error(f"Path security error: {e}")
        return {"documents": [], "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in doc_ingest: {e}", exc_info=True)
        return {"documents": [], "error": f"Unexpected error: {str(e)}"}
