"""Tests for document ingestion skill.

Covers helper functions, security validation, and binary extractors.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uar.skills.doc_ingest import (
    _is_relative_to,
    _ensure_production_root,
    ALLOWED_EXTENSIONS,
    _extract_pdf,
    _extract_ipynb,
    _extract_docx,
    _extract_xlsx,
    _extract_dataframe,
    _read_file_safely,
    doc_ingest,
)


class TestIsRelativeTo:
    """Path relative-to helper."""

    def test_relative(self):
        base = Path("/home/user")
        path = Path("/home/user/docs/file.txt")
        assert _is_relative_to(path, base) is True

    def test_not_relative(self):
        base = Path("/home/user")
        path = Path("/etc/passwd")
        assert _is_relative_to(path, base) is False

    def test_same_path(self):
        path = Path("/home/user")
        assert _is_relative_to(path, path) is True


class TestEnsureProductionRoot:
    """Production root validation."""

    def test_production_no_root_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("uar.skills.doc_ingest._is_production", True):
                with patch("uar.skills.doc_ingest._allowed_root_env", None):
                    try:
                        _ensure_production_root()
                        assert False, "Expected RuntimeError"
                    except RuntimeError as e:
                        assert "PROJECT_ROOT" in str(e)

    def test_non_production_ok(self):
        with patch("uar.skills.doc_ingest._is_production", False):
            _ensure_production_root()  # Should not raise


class TestAllowedExtensions:
    """Extension whitelist."""

    def test_contains_text(self):
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".md" in ALLOWED_EXTENSIONS

    def test_contains_config(self):
        assert ".json" in ALLOWED_EXTENSIONS
        assert ".yaml" in ALLOWED_EXTENSIONS

    def test_contains_code(self):
        assert ".py" in ALLOWED_EXTENSIONS


class TestExtractPdf:
    """PDF extraction."""

    def test_extract_pdf_success(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page text"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_pdf(pdf_file)
        assert "Page text" in result

    def test_extract_pdf_page_error(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("fail")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_pdf(pdf_file)
        assert "extraction error" in result


class TestExtractIpynb:
    """Jupyter notebook extraction."""

    def test_with_nbformat(self, tmp_path):
        import json

        nb_file = tmp_path / "test.ipynb"
        nb_data = {
            "cells": [
                {"cell_type": "markdown", "source": "# Hello"},
                {"cell_type": "code", "source": "print(1)"},
            ],
            "metadata": {
                "kernelspec": {"language": "python"}
            },
        }
        nb_file.write_text(json.dumps(nb_data))
        with patch("nbformat.read", return_value=nb_data):
            result = _extract_ipynb(nb_file)
        assert "# Hello" in result
        assert "```python" in result

    def test_fallback_json(self, tmp_path):
        import json

        nb_file = tmp_path / "test.ipynb"
        nb_data = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Title"]},
                {"cell_type": "code", "source": ["x = 1"]},
            ],
        }
        nb_file.write_text(json.dumps(nb_data))
        with patch("nbformat.read", side_effect=ImportError):
            result = _extract_ipynb(nb_file)
        assert "# Title" in result
        assert "```python" in result

    def test_invalid_json(self, tmp_path):
        nb_file = tmp_path / "test.ipynb"
        nb_file.write_text("not json")
        with patch("nbformat.read", side_effect=Exception("fail")):
            result = _extract_ipynb(nb_file)
        assert "parse failed" in result


class TestExtractDocx:
    """DOCX extraction."""

    def test_extract_docx(self, tmp_path):
        docx_file = tmp_path / "test.docx"
        docx_file.write_text("fake docx")
        mock_para = MagicMock()
        mock_para.text = "Paragraph text"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []
        with patch("docx.Document", return_value=mock_doc):
            result = _extract_docx(docx_file)
        assert "Paragraph text" in result


class TestExtractXlsx:
    """XLSX extraction."""

    def test_extract_xlsx(self, tmp_path):
        xlsx_file = tmp_path / "test.xlsx"
        xlsx_file.write_bytes(b"PK\x03\x04 fake xlsx")
        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            ("col1", "col2"),
            ("a", "b"),
        ]
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__enter__ = MagicMock(return_value=mock_wb)
        mock_wb.__exit__ = MagicMock(return_value=None)
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = _extract_xlsx(xlsx_file)
        assert "Sheet1" in result
        assert "col1" in result


class TestExtractDataframe:
    """Parquet/Feather extraction."""

    def test_parquet(self, tmp_path):
        pq_file = tmp_path / "test.parquet"
        pq_file.write_bytes(b"fake parquet")
        mock_df = MagicMock()
        mock_df.shape = (100, 3)
        mock_df.columns = ["a", "b", "c"]
        mock_df.head.return_value = mock_df
        mock_df.to_csv.return_value = "a,b,c\n1,2,3"
        with patch("pandas.read_parquet", return_value=mock_df):
            result = _extract_dataframe(pq_file, "parquet")
        assert "shape=(100, 3)" in result
        assert "a,b,c" in result

    def test_feather(self, tmp_path):
        feather_file = tmp_path / "test.feather"
        feather_file.write_bytes(b"fake feather")
        mock_df = MagicMock()
        mock_df.shape = (50, 2)
        mock_df.columns = ["x", "y"]
        mock_df.head.return_value = mock_df
        mock_df.to_csv.return_value = "x,y\n1,2"
        with patch("pandas.read_feather", return_value=mock_df):
            result = _extract_dataframe(feather_file, "feather")
        assert "shape=(50, 2)" in result

    def test_unknown_kind(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported"):
            _extract_dataframe(tmp_path / "test.unknown", "unknown")


class TestReadFileSafely:
    """_read_file_safely with binary extractors."""

    def test_pdf_file(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        pdf = safe / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        with patch("pypdf.PdfReader") as MockReader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "PDF content"
            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]
            MockReader.return_value = mock_reader
            result = _read_file_safely(pdf, safe)
        assert result["type"] == "pdf"
        assert "PDF content" in result["text"]

    def test_ipynb_file(self, tmp_path):
        import json

        safe = tmp_path / "safe"
        safe.mkdir()
        nb = safe / "test.ipynb"
        nb.write_text(json.dumps({"cells": [], "metadata": {}}))
        with patch(
            "nbformat.read", return_value={"cells": [], "metadata": {}}
        ):
            result = _read_file_safely(nb, safe)
        assert result["type"] == "ipynb"

    def test_extraction_failure(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        docx = safe / "test.docx"
        docx.write_text("fake")
        with patch("docx.Document", side_effect=Exception("fail")):
            result = _read_file_safely(docx, safe)
        assert "Extraction failed" in result["error"]

    def test_unicode_decode_error(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        bad = safe / "test.txt"
        bad.write_bytes(b"\x00\xff\x80")
        with patch("builtins.open", side_effect=UnicodeDecodeError(
            "utf-8", b"\x00", 0, 1, "invalid start byte"
        )):
            result = _read_file_safely(bad, safe)
        assert "encoding error" in result["error"].lower()


class TestDocIngest:
    """Main doc_ingest skill function."""

    def test_no_input_path(self):
        from uar.core.contracts import GoalSpec, PipelineContext

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={},
        )
        ctx = PipelineContext(goal=goal)
        result = doc_ingest(ctx)
        assert result["warning"] == "No input_path provided"
        assert result["documents"] == []

    def test_single_file(self, tmp_path):
        from uar.core.contracts import GoalSpec, PipelineContext

        safe = tmp_path / "safe"
        safe.mkdir()
        doc = safe / "hello.txt"
        doc.write_text("world")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            goal = GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={"input_path": str(doc)},
            )
            ctx = PipelineContext(goal=goal)
            result = doc_ingest(ctx)
        assert result["document_count"] == 1
        assert result["documents"][0]["text"] == "world"

    def test_directory(self, tmp_path):
        from uar.core.contracts import GoalSpec, PipelineContext

        safe = tmp_path / "safe"
        safe.mkdir()
        (safe / "a.txt").write_text("A")
        (safe / "b.txt").write_text("B")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            goal = GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={"input_path": str(safe)},
            )
            ctx = PipelineContext(goal=goal)
            result = doc_ingest(ctx)
        assert result["document_count"] == 2
        paths = result["paths"]
        assert any("a.txt" in p for p in paths)
        assert any("b.txt" in p for p in paths)

    def test_nonexistent_path(self):
        from uar.core.contracts import GoalSpec, PipelineContext

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", Path("/tmp")):
            goal = GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={"input_path": "/tmp/nonexistent_path_xyz"},
            )
            ctx = PipelineContext(goal=goal)
            result = doc_ingest(ctx)
        assert result["document_count"] == 0
        assert "Input path not found" in result["errors"]

    def test_path_security_error(self):
        from uar.core.contracts import GoalSpec, PipelineContext

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", Path("/tmp/safe")):
            goal = GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={"input_path": "/etc/passwd"},
            )
            ctx = PipelineContext(goal=goal)
            result = doc_ingest(ctx)
        assert result["status"] == "failed"
        assert "security" in result["error"].lower()
