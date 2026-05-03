from pathlib import Path
from typing import Dict, List

from uar.core.registry import register_skill
from uar.core.exceptions import PathSecurityError
from uar.core.validation import validate_path_security

ALLOWED_ROOT = Path('.').resolve()
ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".ts", ".tsx", ".json", ".js", ".jsx", ".yaml", ".yml"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES = 1000


@register_skill("doc_ingest")
def doc_ingest(ctx):
    """Ingest documents from a specified path with security validation"""
    input_path = ctx.goal.metadata.get("input_path")
    if not input_path:
        return {"documents": [], "warning": "No input_path provided"}

    try:
        path = Path(input_path).resolve()
        
        # Validate path security
        validate_path_security(path, ALLOWED_ROOT)
        
        documents: List[Dict[str, str]] = []

        if path.is_file():
            if path.suffix.lower() in ALLOWED_EXTENSIONS:
                # Check file size
                if path.stat().st_size > MAX_FILE_SIZE:
                    return {"documents": [], "error": f"File too large: {path}"}
                
                try:
                    content = path.read_text(encoding="utf-8")
                    documents.append({
                        "path": str(path.relative_to(ALLOWED_ROOT)),
                        "text": content,
                        "size": len(content)
                    })
                except UnicodeDecodeError:
                    return {"documents": [], "error": f"File encoding error: {path}"}
            else:
                return {"documents": [], "warning": f"Unsupported file type: {path.suffix}"}
                
        elif path.is_dir():
            file_count = 0
            for item in sorted(path.rglob("*")):
                if file_count >= MAX_FILES:
                    documents.append({"path": "LIMIT_EXCEEDED", "text": f"Stopped at {MAX_FILES} files"})
                    break
                    
                if item.is_file() and item.suffix.lower() in ALLOWED_EXTENSIONS:
                    # Check file size
                    if item.stat().st_size > MAX_FILE_SIZE:
                        continue  # Skip large files
                        
                    try:
                        content = item.read_text(encoding="utf-8")
                        documents.append({
                            "path": str(item.relative_to(ALLOWED_ROOT)),
                            "text": content,
                            "size": len(content)
                        })
                        file_count += 1
                    except UnicodeDecodeError:
                        # Skip files with encoding issues
                        continue
                    except PermissionError:
                        # Skip files we can't read
                        continue
        else:
            return {"documents": [], "warning": f"Input path not found: {input_path}"}

        return {
            "documents": documents,
            "document_count": len(documents),
            "paths": [doc["path"] for doc in documents],
            "total_size": sum(doc.get("size", 0) for doc in documents),
        }
        
    except PathSecurityError as e:
        return {"documents": [], "error": str(e)}
    except Exception as e:
        return {"documents": [], "error": f"Unexpected error: {str(e)}"}
