"""Tests for enhanced document ingestion skill.

Covers DocumentElement, extraction helpers, _read_file_enhanced,
_yield_documents_enhanced, and the skill entry point.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.core.exceptions import PathSecurityError
from uar.skills.doc_ingest_enhanced import (
    ALLOWED_EXTENSIONS,
    DocumentElement,
    ProcessingStrategy,
    _extract_with_fallback,
    extract_document,
    _read_file_enhanced,
    _yield_documents_enhanced,
    doc_ingest_enhanced,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestDocumentElement:
    """DocumentElement dataclass."""

    def test_to_dict(self):
        el = DocumentElement(
            element_type="Text",
            text="hello",
            metadata={"page": 1},
            page_number=2,
            coordinates=[0, 0, 100, 100],
        )
        d = el.to_dict()
        assert d["type"] == "Text"
        assert d["text"] == "hello"
        assert d["metadata"]["page"] == 1
        assert d["page_number"] == 2

    def test_defaults(self):
        el = DocumentElement(element_type="Title", text="title")
        d = el.to_dict()
        assert d["metadata"] == {}
        assert d["page_number"] is None
        assert d["coordinates"] is None


class TestExtractWithFallback:
    """Fallback text extraction."""

    def test_reads_text_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("hello world")
            path = f.name
        try:
            result = _extract_with_fallback(Path(path))
            assert len(result) == 1
            assert result[0].text == "hello world"
            assert result[0].element_type == "Text"
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        with pytest.raises(Exception):
            _extract_with_fallback(Path("/nonexistent/file.txt"))


class TestExtractDocument:
    """Strategy-based extraction routing."""

    def test_fallback_strategy(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("test content")
            path = f.name
        try:
            result = extract_document(
                Path(path), strategy=ProcessingStrategy.FALLBACK
            )
            assert len(result) == 1
            assert result[0].text == "test content"
        finally:
            os.unlink(path)

    def test_auto_selects_fallback_when_no_deps(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("auto test")
            path = f.name
        try:
            with patch(
                "uar.skills.doc_ingest_enhanced.DOCLING_AVAILABLE", False
            ):
                with patch(
                    "uar.skills.doc_ingest_enhanced.UNSUPPORTED_AVAILABLE",
                    False,
                ):
                    result = extract_document(
                        Path(path), strategy=ProcessingStrategy.AUTO
                    )
            assert len(result) == 1
        finally:
            os.unlink(path)


class TestReadFileEnhanced:
    """Enhanced file reading with validation."""

    def test_valid_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("hello")
            result = _read_file_enhanced(path, Path(tmp))
            assert result["text"] == "hello"
            assert result["size"] == 5
            assert result["type"] == "txt"

    def test_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.unknown"
            path.write_text("x")
            result = _read_file_enhanced(path, Path(tmp))
            assert result["error"] == "Unsupported file type"

    def test_file_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "huge.txt"
            path.write_text("x" * 100)
            with patch(
                "uar.skills.doc_ingest_enhanced.MAX_FILE_SIZE", 10
            ):
                result = _read_file_enhanced(path, Path(tmp))
            assert result["error"] == "File too large"

    def test_path_security_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secret.txt"
            path.write_text("x")
            with patch(
                "uar.skills.doc_ingest_enhanced.validate_path_security",
                side_effect=PathSecurityError(str(path), "forbidden"),
            ):
                result = _read_file_enhanced(path, Path(tmp))
            assert result["error"] == "Path security error"

    def test_extraction_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("fallback content")
            with patch(
                "uar.skills.doc_ingest_enhanced.extract_document",
                side_effect=RuntimeError("boom"),
            ):
                result = _read_file_enhanced(path, Path(tmp))
            assert "fallback" in result.get("warning", "")
            assert result["text"] == "fallback content"


class TestYieldDocumentsEnhanced:
    """Document yield generator."""

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("hello")
            docs = list(_yield_documents_enhanced(path, Path(tmp)))
            assert len(docs) == 1
            assert docs[0]["text"] == "hello"

    def test_unsupported_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.bin"
            path.write_bytes(b"\x00")
            docs = list(_yield_documents_enhanced(path, Path(tmp)))
            assert len(docs) == 1
            assert docs[0]["error"] == "Unsupported file type"

    def test_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a")
            (Path(tmp) / "b.txt").write_text("b")
            docs = list(_yield_documents_enhanced(Path(tmp), Path(tmp)))
            assert len(docs) == 2

    def test_nonexistent_path(self):
        docs = list(
            _yield_documents_enhanced(
                Path("/nonexistent"), Path("/tmp")
            )
        )
        assert len(docs) == 1
        assert docs[0]["error"] == "Input path not found"

    def test_max_files_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                (Path(tmp) / f"{i}.txt").write_text("x")
            with patch(
                "uar.skills.doc_ingest_enhanced.MAX_FILES", 2
            ):
                docs = list(
                    _yield_documents_enhanced(Path(tmp), Path(tmp))
                )
            limit_doc = [d for d in docs if d.get("path") == "LIMIT_EXCEEDED"]
            assert len(limit_doc) == 1

    def test_file_too_large_in_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.txt"
            path.write_text("x" * 100)
            with patch(
                "uar.skills.doc_ingest_enhanced.MAX_FILE_SIZE", 10
            ):
                docs = list(
                    _yield_documents_enhanced(Path(tmp), Path(tmp))
                )
            assert any(d.get("error") == "File too large" for d in docs)


class TestDocIngestEnhancedSkill:
    """Skill entry point."""

    def test_no_input_path(self):
        result = doc_ingest_enhanced(_ctx({}))
        assert result["documents"] == []
        assert "warning" in result

    def test_invalid_strategy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_resolved = Path(tmp).resolve()
            path = tmp_resolved / "test.txt"
            path.write_text("hello")
            with patch(
                "uar.skills.doc_ingest_enhanced.ALLOWED_ROOT",
                tmp_resolved,
            ):
                result = doc_ingest_enhanced(
                    _ctx({
                        "input_path": str(path),
                        "processing_strategy": "invalid",
                    })
                )
        assert "document_count" in result

    def test_path_security_error(self):
        with patch(
            "uar.skills.doc_ingest_enhanced.validate_path_security",
            side_effect=PathSecurityError("/etc/passwd", "forbidden"),
        ):
            result = doc_ingest_enhanced(
                _ctx({"input_path": "/etc/passwd"})
            )
        assert result["status"] == "failed"

    def test_basic_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_resolved = Path(tmp).resolve()
            path = tmp_resolved / "test.txt"
            path.write_text("hello world")
            with patch(
                "uar.skills.doc_ingest_enhanced.ALLOWED_ROOT",
                tmp_resolved,
            ):
                result = doc_ingest_enhanced(
                    _ctx({"input_path": str(path)})
                )
        assert result["document_count"] == 1
        assert result["total_size"] > 0
        assert result["documents"][0]["text"] == "hello world"

    def test_allowed_extensions(self):
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".py" in ALLOWED_EXTENSIONS
        assert ".ipynb" in ALLOWED_EXTENSIONS
