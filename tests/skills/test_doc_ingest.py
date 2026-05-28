"""Tests for document ingestion skill.

Covers helper functions and security validation.
"""

from pathlib import Path
from unittest.mock import patch

from uar.skills.doc_ingest import (
    _is_relative_to,
    _ensure_production_root,
    ALLOWED_EXTENSIONS,
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
