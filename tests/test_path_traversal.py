"""Regression tests for path-traversal protection in file endpoints."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from uar.api.server import _resolve_docs_path
from uar.core.exceptions import PathSecurityError, ValidationError


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Inject test API key so authenticated endpoints work."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


class TestResolveDocsPath:
    """Unit tests for the _resolve_docs_path helper."""

    def test_resolves_relative_path(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))
        (root / "docs").mkdir()

        resolved = _resolve_docs_path("docs")
        # samefile handles symlinked temp dirs (macOS /var → /private/var)
        assert resolved.samefile(root / "docs")

    def test_rejects_traversal_dotdot(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        with pytest.raises(PathSecurityError):
            _resolve_docs_path("../etc/passwd")

    def test_rejects_traversal_absolute_outside(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        with pytest.raises(PathSecurityError):
            _resolve_docs_path("/etc/passwd")

    def test_rejects_null_bytes(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        with pytest.raises(PathSecurityError):
            _resolve_docs_path("foo\x00bar")

    def test_rejects_empty_path(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        with pytest.raises(ValidationError):
            _resolve_docs_path("")

    @pytest.mark.skipif(
        not hasattr(os, "symlink"),
        reason="Platform does not support symlinks",
    )
    def test_rejects_symlink_outside(self, monkeypatch):
        """A symlink inside PROJECT_ROOT pointing outside must be rejected."""
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        secret = root / "secret.txt"
        secret.write_text("secret")
        link = root / "link_to_secret"
        try:
            link.symlink_to(secret)
        except OSError:
            pytest.skip("Symlink creation not supported")

        # Symlink to a file INSIDE root is allowed
        resolved = _resolve_docs_path("link_to_secret")
        assert resolved.samefile(secret)

        # Symlink to a file OUTSIDE root is rejected
        outside = Path(tempfile.mkdtemp()) / "outside.txt"
        outside.write_text("outside")
        bad_link = root / "bad_link"
        try:
            bad_link.symlink_to(outside)
        except OSError:
            pytest.skip("Symlink creation not supported")

        with pytest.raises(PathSecurityError):
            _resolve_docs_path("bad_link")

    def test_rejects_traversal_in_middle(self, monkeypatch):
        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))
        (root / "a" / "b").mkdir(parents=True)

        with pytest.raises(PathSecurityError):
            _resolve_docs_path("a/../../etc/passwd")


class TestBrowseSymlinkSkipping:
    """Verify docs_browse skips symlinks instead of following them."""

    @pytest.mark.skipif(
        not hasattr(os, "symlink"),
        reason="Platform does not support symlinks",
    )
    def test_browse_skips_symlinks(self, monkeypatch):
        """Symlinks inside the browsed tree must not appear in results."""
        from fastapi.testclient import TestClient
        from uar.api.server import app

        root = Path(tempfile.mkdtemp())
        monkeypatch.setenv("PROJECT_ROOT", str(root))

        # Create real file and symlink
        (root / "real_file.txt").write_text("real")
        link = root / "link_to_real"
        try:
            link.symlink_to(root / "real_file.txt")
        except OSError:
            pytest.skip("Symlink creation not supported")

        client = TestClient(app)
        r = client.get(
            "/api/uar/docs/browse",
            params={"path": str(root)},
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert r.status_code == 200
        data = r.json()
        names = {e["name"] for e in data["entries"]}
        assert "real_file.txt" in names
        assert "link_to_real" not in names
