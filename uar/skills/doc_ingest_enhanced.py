"""
Enhanced document ingestion skill using Unstructured and Docling for advanced document processing.

This module provides enhanced document processing capabilities including:
- Layout-aware document parsing with Unstructured
- Advanced PDF understanding with Docling
- OCR support for scanned documents
- Table extraction and preservation
- Multi-format support
- Better error handling and recovery
"""  # noqa: E501

import os
from pathlib import Path
from typing import Any, Generator, Optional, List, Dict
import logging
from enum import Enum

try:
    from unstructured.partition.auto import partition
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.image import partition_image
    from unstructured.partition.docx import partition_docx
    from unstructured.partition.xlsx import partition_xlsx
    from unstructured.partition.html import partition_html
    from unstructured.partition.md import partition_md
    from unstructured.partition.pptx import partition_pptx

    UNSUPPORTED_AVAILABLE = True
except ImportError:
    UNSUPPORTED_AVAILABLE = False
    logging.warning(
        "Unstructured not available. Install with: pip install unstructured[local-inference]"  # noqa: E501
    )

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available. Install with: pip install docling")

from uar.core.registry import register_skill
from uar.core.exceptions import PathSecurityError
from uar.core.skill_utils import skill_guard
from uar.core.validation import validate_path_security


logger = logging.getLogger(__name__)

# Constants
FILE_SIZE_LIMIT_MB = 50  # Increased from 10MB for Unstructured
MAX_FILE_SIZE = FILE_SIZE_LIMIT_MB * 1024 * 1024
MAX_FILES = 1000
TOTAL_SIZE_LIMIT_MB = 500  # Increased for better processing
MAX_TOTAL_SIZE = TOTAL_SIZE_LIMIT_MB * 1024 * 1024

# Resolve allowed root
_allowed_root_env = os.getenv("PROJECT_ROOT") or os.getenv("RUNS_DIR")
ALLOWED_ROOT = (
    Path(_allowed_root_env).resolve() if _allowed_root_env else Path.cwd()
)

# Enhanced extensions list
ALLOWED_EXTENSIONS = {
    # Documents
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".odt",
    ".rtf",
    # Text
    ".txt",
    ".md",
    ".rst",
    ".markdown",
    ".html",
    ".htm",
    ".xml",
    # Data
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    # Spreadsheets
    ".xlsx",
    ".xls",
    ".ods",
    # Images (for OCR)
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
    # Code
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".go",
    ".rs",
    # Notebooks
    ".ipynb",
}


class ProcessingStrategy(Enum):
    """Strategy for document processing."""

    UNSUPPORTED = "unstructured"  # Use Unstructured library
    DOCLING = "docling"  # Use Docling for advanced PDF parsing
    FALLBACK = "fallback"  # Use original simple parsing
    AUTO = "auto"  # Automatically choose best strategy


class DocumentElement:
    """Represents a structured document element."""

    def __init__(
        self,
        element_type: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        page_number: Optional[int] = None,
        coordinates: Optional[List[float]] = None,
    ):
        self.element_type = element_type
        self.text = text
        self.metadata = metadata or {}
        self.page_number = page_number
        self.coordinates = coordinates

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.element_type,
            "text": self.text,
            "metadata": self.metadata,
            "page_number": self.page_number,
            "coordinates": self.coordinates,
        }


def _extract_with_unstructured(
    file_path: Path, strategy: str = "auto", **kwargs
) -> List[DocumentElement]:
    """Extract document elements using Unstructured library.

    Args:
        file_path: Path to the document
        strategy: Processing strategy
        **kwargs: Additional arguments for Unstructured partition functions

    Returns:
        List of DocumentElement objects
    """
    if not UNSUPPORTED_AVAILABLE:
        raise RuntimeError("Unstructured not installed")

    elements = []

    try:
        # Determine partition function based on file type
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            # Use advanced PDF partitioning
            elements_list = partition_pdf(
                str(file_path),
                strategy="hi_res" if strategy == "auto" else strategy,
                extract_images_in_pdf=True,
                infer_table_structure=True,
                **kwargs,
            )
        elif suffix == ".docx":
            elements_list = partition_docx(str(file_path), **kwargs)
        elif suffix in [".xlsx", ".xls"]:
            elements_list = partition_xlsx(str(file_path), **kwargs)
        elif suffix in [".html", ".htm"]:
            elements_list = partition_html(str(file_path), **kwargs)
        elif suffix == ".md":
            elements_list = partition_md(str(file_path), **kwargs)
        elif suffix in [".pptx", ".ppt"]:
            elements_list = partition_pptx(str(file_path), **kwargs)
        elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            elements_list = partition_image(str(file_path), **kwargs)
        else:
            # Use auto partition for other types
            elements_list = partition(str(file_path), **kwargs)

        # Convert Unstructured elements to DocumentElement
        for el in elements_list:
            doc_el = DocumentElement(
                element_type=str(el.category),
                text=str(el),
                metadata={
                    "element_id": str(el.id) if hasattr(el, "id") else None,
                    "parent_id": str(el.parent_id)
                    if hasattr(el, "parent_id")
                    else None,
                },
                page_number=getattr(el, "page_number", None),
                coordinates=getattr(el, "coordinates", None),
            )
            elements.append(doc_el)

        logger.info(
            "Extracted %s elements from %s using Unstructured",
            len(elements),
            file_path,
        )
        return elements

    except Exception:
        logger.exception(
            "Unstructured extraction failed for %s", file_path
        )
        raise


def _extract_with_docling(file_path: Path, **kwargs) -> List[DocumentElement]:
    """Extract document elements using Docling for advanced PDF understanding.

    Args:
        file_path: Path to the document
        **kwargs: Additional arguments for Docling

    Returns:
        List of DocumentElement objects
    """
    if not DOCLING_AVAILABLE:
        raise RuntimeError("Docling not installed")

    try:
        converter = DocumentConverter(
            format_options={
                PdfFormatOption.PDFOCR: True,
            }
        )

        result = converter.convert(str(file_path))

        elements = []

        # Extract text with layout information
        for page in result.document.pages:
            for item in page.content:
                doc_el = DocumentElement(
                    element_type=item.__class__.__name__,
                    text=str(item),
                    metadata={
                        "page_number": page.page_no,
                    },
                    page_number=page.page_no,
                )
                elements.append(doc_el)

        logger.info(
            "Extracted %s elements from %s using Docling",
            len(elements),
            file_path,
        )
        return elements

    except Exception:
        logger.exception("Docling extraction failed for %s", file_path)
        raise


def _extract_with_fallback(file_path: Path) -> List[DocumentElement]:
    """Fallback extraction using simple text reading.

    Args:
        file_path: Path to the document

    Returns:
        List of DocumentElement objects
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return [
            DocumentElement(
                element_type="Text",
                text=content,
                metadata={"source": "fallback"},
            )
        ]
    except Exception:
        logger.exception("Fallback extraction failed for %s", file_path)
        raise


def extract_document(
    file_path: Path,
    strategy: ProcessingStrategy = ProcessingStrategy.AUTO,
    **kwargs,
) -> List[DocumentElement]:
    """Extract structured elements from a document.

    Args:
        file_path: Path to the document
        strategy: Processing strategy to use
        **kwargs: Additional arguments for the extraction method

    Returns:
        List of DocumentElement objects

    Raises:
        RuntimeError: If required libraries are not available
        Exception: If extraction fails
    """
    suffix = file_path.suffix.lower()

    # Auto-select strategy
    if strategy == ProcessingStrategy.AUTO:
        if suffix == ".pdf" and DOCLING_AVAILABLE:
            strategy = ProcessingStrategy.DOCLING
        elif UNSUPPORTED_AVAILABLE:
            strategy = ProcessingStrategy.UNSUPPORTED
        else:
            strategy = ProcessingStrategy.FALLBACK

    # Execute extraction based on strategy
    if strategy == ProcessingStrategy.DOCLING:
        return _extract_with_docling(file_path, **kwargs)
    elif strategy == ProcessingStrategy.UNSUPPORTED:
        return _extract_with_unstructured(file_path, **kwargs)
    else:
        return _extract_with_fallback(file_path)


def _read_file_enhanced(
    file_path: Path,
    allowed_root: Path,
    strategy: ProcessingStrategy = ProcessingStrategy.AUTO,
) -> Dict[str, Any]:
    """Enhanced file reading with advanced document processing.

    Args:
        file_path: Path to the file
        allowed_root: Allowed root directory for security
        strategy: Processing strategy to use

    Returns:
        Dictionary with extracted content and metadata
    """
    try:
        # Validate security
        validate_path_security(file_path, allowed_root)

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return {
                "path": str(file_path.relative_to(allowed_root)),
                "text": "",
                "size": 0,
                "error": "File too large",
            }

        suffix = file_path.suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            return {
                "path": str(file_path.relative_to(allowed_root)),
                "text": "",
                "size": 0,
                "error": "Unsupported file type",
            }

        # Extract document elements
        try:
            elements = extract_document(file_path, strategy=strategy)

            # Combine elements into text
            text_parts = []
            for el in elements:
                if el.text.strip():
                    text_parts.append(el.text)

            text = "\n\n".join(text_parts)

            return {
                "path": str(file_path.relative_to(allowed_root)),
                "text": text,
                "size": len(text),
                "type": suffix.lstrip("."),
                "elements": [el.to_dict() for el in elements],
                "element_count": len(elements),
                "processing_strategy": strategy.value,
            }

        except Exception as e:
            # Fall back to simple text reading on error
            logger.warning(
                f"Advanced extraction failed for {file_path}, falling back: {e}"  # noqa: E501
            )
            try:
                with open(
                    file_path, "r", encoding="utf-8", errors="replace"
                ) as f:
                    content = f.read()
                return {
                    "path": str(file_path.relative_to(allowed_root)),
                    "text": content,
                    "size": len(content),
                    "type": suffix.lstrip("."),
                    "warning": "Advanced extraction failed, used fallback",
                }
            except Exception:
                logger.exception(
                    "Both advanced and fallback extraction failed for %s",
                    file_path,
                )
                return {
                    "path": str(file_path.relative_to(allowed_root)),
                    "text": "",
                    "size": 0,
                    "error": "Extraction failed",
                }

    except PathSecurityError:
        logger.warning("Path security error")
        return {
            "path": str(file_path.relative_to(allowed_root))
            if file_path.is_relative_to(allowed_root)
            else str(file_path),
            "text": "",
            "size": 0,
            "error": "Path security error",
        }
    except Exception:
        logger.exception("Unexpected error reading %s", file_path)
        return {
            "path": str(file_path.relative_to(allowed_root))
            if file_path.is_relative_to(allowed_root)
            else str(file_path),
            "text": "",
            "size": 0,
            "error": "Read error",
        }


def _yield_documents_enhanced(
    path: Path,
    allowed_root: Path,
    strategy: ProcessingStrategy = ProcessingStrategy.AUTO,
) -> Generator[Dict[str, Any], None, None]:
    """Generator to yield documents with enhanced processing.

    Args:
        path: Path to file or directory
        allowed_root: Allowed root directory
        strategy: Processing strategy to use

    Yields:
        Document dictionaries
    """
    file_count = 0
    total_size = 0

    if path.is_file():
        if path.suffix.lower() in ALLOWED_EXTENSIONS:
            doc = _read_file_enhanced(path, allowed_root, strategy)
            yield doc
        else:
            yield {
                "path": str(path.relative_to(allowed_root))
                if path.is_relative_to(allowed_root)
                else str(path),
                "text": "",
                "size": 0,
                "error": "Unsupported file type",
            }
    elif path.is_dir():
        for entry in path.rglob("*"):
            if file_count >= MAX_FILES:
                yield {
                    "path": "LIMIT_EXCEEDED",
                    "text": f"Stopped at {MAX_FILES} files",
                    "size": 0,
                    "warning": "Maximum file count reached",
                }
                return

            if total_size >= MAX_TOTAL_SIZE:
                yield {
                    "path": "SIZE_LIMIT_EXCEEDED",
                    "text": f"Stopped at {total_size} bytes",
                    "size": 0,
                    "warning": "Maximum total size reached",
                }
                return

            if entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    entry_size = entry.stat().st_size
                    if entry_size > MAX_FILE_SIZE:
                        yield {
                            "path": str(entry.relative_to(allowed_root))
                            if entry.is_relative_to(allowed_root)
                            else str(entry),
                            "text": "",
                            "size": 0,
                            "error": "File too large",
                        }
                        file_count += 1
                        continue

                    doc = _read_file_enhanced(entry, allowed_root, strategy)
                    file_count += 1

                    if "error" not in doc or doc["error"] == "":
                        total_size += doc.get("size", 0)

                    yield doc

                except OSError:
                    logger.warning("File access error for %s", entry)
                    continue
    else:
        yield {
            "path": str(path),
            "text": "",
            "size": 0,
            "error": "Input path not found",
        }


@register_skill("doc_ingest_enhanced")
@skill_guard("Doc ingest enhanced", status="failed")
def doc_ingest_enhanced(ctx):
    """Enhanced document ingestion with advanced processing capabilities.

    Features:
    - Layout-aware document parsing with Unstructured
    - Advanced PDF understanding with Docling
    - OCR support for scanned documents
    - Table extraction and preservation
    - Structured element extraction
    - Multiple processing strategies
    - Better error handling and recovery

    Args:
        ctx: Skill execution context

    Returns:
        Dictionary with processed documents and metadata
    """
    input_path = ctx.goal.metadata.get("input_path")
    if not input_path:
        return {"documents": [], "warning": "No input_path provided"}

    # Get processing strategy from metadata
    strategy_str = ctx.goal.metadata.get("processing_strategy", "auto")
    try:
        strategy = ProcessingStrategy(strategy_str)
    except ValueError:
        strategy = ProcessingStrategy.AUTO
        logger.warning("Invalid strategy %s, using AUTO", strategy_str)

    try:
        path = Path(input_path).resolve()

        # Validate path security
        validate_path_security(path, ALLOWED_ROOT)

        # Process documents
        documents = []
        total_size = 0
        doc_count = 0
        element_count = 0

        for doc in _yield_documents_enhanced(path, ALLOWED_ROOT, strategy):
            if doc_count >= MAX_FILES:
                documents.append(doc)
                break

            documents.append(doc)
            doc_count += 1

            if "error" not in doc or doc.get("error") == "":
                total_size += doc.get("size", 0)
                element_count += doc.get("element_count", 0)

        return {
            "documents": documents,
            "document_count": len(
                [
                    doc
                    for doc in documents
                    if "error" not in doc or doc.get("error") == ""
                ]
            ),
            "paths": [
                doc["path"]
                for doc in documents
                if "error" not in doc or doc.get("error") == ""
            ],
            "total_size": total_size,
            "total_elements": element_count,
            "processing_strategy": strategy.value,
            "errors": [
                doc["error"]
                for doc in documents
                if "error" in doc and doc["error"]
            ],
            "warnings": [
                doc["warning"]
                for doc in documents
                if "warning" in doc and doc["warning"]
            ],
        }

    except PathSecurityError:
        return {"documents": [], "error": "Path security error"}
