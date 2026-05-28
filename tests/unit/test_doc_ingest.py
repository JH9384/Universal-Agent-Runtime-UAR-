"""Comprehensive unit tests for the doc_ingest skill.

Covers file ingestion, directory traversal, security validation,
error handling, and resource limits.
"""

from unittest.mock import patch

import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.doc_ingest import doc_ingest, ALLOWED_EXTENSIONS


@pytest.fixture
def make_ctx(tmp_path):
    """Factory that creates a PipelineContext with input_path metadata."""

    def _make(input_path: str):
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={"input_path": str(input_path)},
        )
        return PipelineContext(goal=goal)

    return _make


class TestDocIngestSingleFile:
    """Ingesting individual files."""

    def test_ingest_txt_file(self, tmp_path, make_ctx):
        file = tmp_path / "hello.txt"
        file.write_text("Hello world")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 1
        assert result["documents"][0]["text"] == "Hello world"
        assert result["documents"][0]["path"] == "hello.txt"

    def test_ingest_python_file(self, tmp_path, make_ctx):
        file = tmp_path / "script.py"
        file.write_text("print('hi')")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 1
        assert "print('hi')" in result["documents"][0]["text"]

    def test_ingest_unsupported_extension(self, tmp_path, make_ctx):
        file = tmp_path / "data.xyz"
        file.write_text("secret")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 0
        assert result["documents"][0]["error"] == "Unsupported file type"

    def test_ingest_nonexistent_file(self, tmp_path, make_ctx):
        file = tmp_path / "missing.txt"

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 0
        assert result["documents"][0]["error"] == "Input path not found"

    def test_ingest_empty_file(self, tmp_path, make_ctx):
        file = tmp_path / "empty.md"
        file.write_text("")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 1
        assert result["documents"][0]["text"] == ""

    def test_ingest_file_with_encoding_errors(self, tmp_path, make_ctx):
        file = tmp_path / "binary.txt"
        file.write_bytes(b"\xff\xfe\x00\x01")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(file))

        assert result["document_count"] == 1
        # errors="replace" should handle invalid UTF-8
        assert "\ufffd" in result["documents"][0]["text"]


class TestDocIngestDirectory:
    """Ingesting directories recursively."""

    def test_ingest_directory(self, tmp_path, make_ctx):
        (tmp_path / "a.txt").write_text("A")
        (tmp_path / "b.py").write_text("B")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("C")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(tmp_path))

        texts = {d["text"] for d in result["documents"]}
        assert "A" in texts
        assert "B" in texts
        assert "C" in texts
        assert result["document_count"] == 3

    def test_ingest_skips_unsupported_files(self, tmp_path, make_ctx):
        (tmp_path / "good.txt").write_text("OK")
        (tmp_path / "bad.exe").write_text("virus")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(tmp_path))

        assert result["document_count"] == 1
        assert result["documents"][0]["text"] == "OK"

    def test_ingest_empty_directory(self, tmp_path, make_ctx):
        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(tmp_path))

        assert result["document_count"] == 0


class TestDocIngestSecurity:
    """Path security validation."""

    def test_path_outside_allowed_root(self, tmp_path, make_ctx):
        outside = tmp_path / ".." / "outside.txt"

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(outside))

        assert result.get("error") == "Path security error"
        assert result["documents"] == []

    def test_absolute_path_outside_root(self, tmp_path, make_ctx):
        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx("/etc/passwd"))

        assert result.get("error") == "Path security error"


class TestDocIngestLimits:
    """Resource limit handling."""

    def test_file_size_limit(self, tmp_path, make_ctx):
        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * (11 * 1024 * 1024))

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(big))

        assert result["document_count"] == 0
        assert "too large" in result["documents"][0]["error"].lower()

    def test_max_files_limit(self, tmp_path, make_ctx):
        for i in range(1005):
            (tmp_path / f"f{i}.txt").write_text("x")

        with patch(
            "uar.skills.doc_ingest.ALLOWED_ROOT", tmp_path.resolve()
        ):
            result = doc_ingest(make_ctx(tmp_path))

        # Should stop at MAX_FILES and include a LIMIT_EXCEEDED marker
        assert any(
            d.get("warning") == "Maximum file count reached"
            for d in result["documents"]
        )


class TestDocIngestInputValidation:
    """Input edge cases."""

    def test_missing_input_path(self, tmp_path, make_ctx):
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={},
        )
        ctx = PipelineContext(goal=goal)

        result = doc_ingest(ctx)
        assert result["documents"] == []
        assert "No input_path" in result.get("warning", "")

    def test_allowed_extensions_coverage(self):
        """Sanity check: ALLOWED_EXTENSIONS should be a non-empty set."""
        assert len(ALLOWED_EXTENSIONS) > 50
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".py" in ALLOWED_EXTENSIONS
        assert ".md" in ALLOWED_EXTENSIONS
