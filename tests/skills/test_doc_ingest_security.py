"""Security-focused tests for doc_ingest skill.

Covers path traversal, symlink attacks, production root validation,
and resource limit enforcement.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.doc_ingest import (
    doc_ingest,
    _read_file_safely,
    _yield_documents,
    _ensure_production_root,
    _is_relative_to,
    MAX_FILE_SIZE,
)


def _ctx(input_path: str) -> PipelineContext:
    goal = GoalSpec(
        id="test",
        user_intent="test",
        objective="test",
        metadata={"input_path": input_path},
    )
    return PipelineContext(goal=goal)


class TestPathTraversalPrevention:
    """Path traversal attack vectors."""

    def test_traversal_outside_root_blocked(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        target = tmp_path / "secret.txt"
        target.write_text("secret")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            # Path resolves outside ALLOWED_ROOT
            result = doc_ingest(_ctx(str(tmp_path / ".." / "secret.txt")))
            assert result["status"] == "failed"
            assert "security" in result["error"].lower()

    def test_absolute_path_outside_root_blocked(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            result = doc_ingest(_ctx("/etc/passwd"))
            assert result["status"] == "failed"

    def test_symlink_to_outside_root_blocked(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")
        link = safe / "link.txt"
        link.symlink_to(secret)

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            result = doc_ingest(_ctx(str(link)))
            # Symlink that resolves outside should be caught
            assert result["status"] == "failed"

    def test_valid_path_inside_root_allowed(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        doc = safe / "doc.txt"
        doc.write_text("hello")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            result = doc_ingest(_ctx(str(doc)))
            assert "status" not in result or result["status"] != "failed"
            assert len(result["documents"]) >= 1


class TestProductionRootValidation:
    """Production environment enforcement."""

    def test_production_without_project_root_raises(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        with patch("uar.skills.doc_ingest._is_production", True):
            with patch("uar.skills.doc_ingest._allowed_root_env", None):
                with pytest.raises(RuntimeError, match="PROJECT_ROOT"):
                    _ensure_production_root()

    def test_non_production_skips_check(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        # Should not raise even without PROJECT_ROOT
        _ensure_production_root()


class TestResourceLimits:
    """Memory and file count limits."""

    def test_max_file_size_respected(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        big = safe / "big.txt"
        big.write_text("x" * (MAX_FILE_SIZE + 1))

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            docs = list(_yield_documents(big, safe))
            assert any("too large" in str(d.get("error", "")) for d in docs)

    def test_max_total_size_respected(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        for i in range(10):
            (safe / f"doc{i}.txt").write_text("x" * 100)

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            # Lower total size limit for testing
            with patch("uar.skills.doc_ingest.MAX_TOTAL_SIZE", 200):
                docs = list(_yield_documents(safe, safe))
                assert any(
                    "SIZE_LIMIT" in str(d.get("path", "")) for d in docs
                )

    def test_max_files_respected(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        for i in range(10):
            (safe / f"doc{i}.txt").write_text("x")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            with patch("uar.skills.doc_ingest.MAX_FILES", 3):
                docs = list(_yield_documents(safe, safe))
                assert any(
                    "LIMIT_EXCEEDED" in str(d.get("path", "")) for d in docs
                )

    def test_unsupported_extension_single_file(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        exe = safe / "script.exe"
        exe.write_text("bad")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            # Single file with unsupported extension reports error
            docs = list(_yield_documents(exe, safe))
            assert any(
                "Unsupported" in str(d.get("error", "")) for d in docs
            )

    def test_unsupported_extension_dir_skipped(self, tmp_path, monkeypatch):
        safe = tmp_path / "safe"
        safe.mkdir()
        (safe / "script.exe").write_text("bad")
        (safe / "doc.txt").write_text("good")

        with patch("uar.skills.doc_ingest.ALLOWED_ROOT", safe):
            # In directory mode unsupported files are silently skipped
            docs = list(_yield_documents(safe, safe))
            paths = [d["path"] for d in docs if "error" not in d]
            assert "doc.txt" in str(paths)
            assert not any("exe" in str(d.get("path", "")) for d in docs)


class TestIsRelativeTo:
    """Python < 3.9 compatibility helper."""

    def test_child_is_relative(self):
        assert _is_relative_to(Path("/a/b"), Path("/a")) is True

    def test_sibling_is_not_relative(self):
        assert _is_relative_to(Path("/a/b"), Path("/c")) is False

    def test_same_path_is_relative(self):
        assert _is_relative_to(Path("/a"), Path("/a")) is True


class TestReadFileSafely:
    """Error handling in _read_file_safely."""

    def test_permission_error(self, tmp_path, monkeypatch):
        safe = tmp_path
        secret = safe / "secret.txt"
        secret.write_text("data")
        secret.chmod(0o000)
        try:
            result = _read_file_safely(secret, safe)
            assert "Permission denied" in result["error"]
        finally:
            secret.chmod(0o644)

    def test_nonexistent_file(self, tmp_path):
        safe = tmp_path
        result = _read_file_safely(safe / "nope.txt", safe)
        assert "Read failed" in result["error"]

    def test_binary_file_encoding_error(self, tmp_path):
        safe = tmp_path
        binary = safe / "binary.bin"
        binary.write_bytes(b"\x00\xff\x80")

        result = _read_file_safely(binary, safe)
        # Binary files yield either content or encoding error
        assert "error" not in result or result["error"] == ""

    def test_relative_path_in_output(self, tmp_path):
        safe = tmp_path
        sub = safe / "sub"
        sub.mkdir()
        doc = sub / "doc.txt"
        doc.write_text("hello")

        result = _read_file_safely(doc, safe)
        assert result["path"] == "sub/doc.txt"
