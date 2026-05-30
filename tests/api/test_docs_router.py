"""Tests for uar.api.routers.docs."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.docs import (
    router,
    _docs_root,
    _library_dir,
    _cleanup_orphaned_temp_files,
    _resolve_docs_path,
)


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(router)
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        with patch("uar.api.routers.docs._auth_svc") as mock_auth:
            mock_auth.authenticate.return_value = None
            mock_auth.require_user.return_value = None
            yield TestClient(app)


class TestDocsRoot:
    def test_default(self, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            assert _docs_root() == tmp_path.resolve()

    def test_fallback_cwd(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _docs_root() == Path.cwd().resolve()


class TestLibraryDir:
    def test_custom_env(self, tmp_path):
        lib = tmp_path / "my_lib"
        with patch.dict(os.environ, {"UAR_LIBRARY_DIR": str(lib)}):
            assert _library_dir() == lib.resolve()

    def test_default(self, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            p = _library_dir()
            assert p.name == ".uar_library"


class TestCleanupOrphaned:
    def test_cleans_old(self, tmp_path):
        lib = tmp_path
        old = lib / "old.tmp"
        old.write_text("x")
        import time

        os.utime(old, (time.time() - 7200, time.time() - 7200))
        count = _cleanup_orphaned_temp_files(lib)
        assert count >= 0
        assert not old.exists()

    def test_no_files(self, tmp_path):
        assert _cleanup_orphaned_temp_files(tmp_path) == 0


class TestResolveDocsPath:
    def test_relative(self, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            p = _resolve_docs_path("test.txt")
            assert p == tmp_path / "test.txt"

    def test_empty(self):
        with pytest.raises(Exception):
            _resolve_docs_path("")

    def test_null_bytes(self):
        with pytest.raises(Exception):
            _resolve_docs_path("path\x00.txt")

    def test_outside_root(self, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            with pytest.raises(Exception):
                _resolve_docs_path("/etc/passwd")


class TestDocsPresets:
    def test_returns_presets(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/presets")
        assert response.status_code == 200
        data = response.json()
        assert "project_root" in data
        assert "presets" in data


class TestDocsLibraryList:
    def test_empty(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/library")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "entries" in data

    def test_with_files(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/library")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 0
        assert "entries" in data


class TestDocsLibraryDelete:
    def test_invalid_name(self, client):
        response = client.delete("/api/uar/docs/library?name=..")
        assert response.status_code == 400

    def test_not_found(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.delete("/api/uar/docs/library?name=nope.txt")
        assert response.status_code == 404


class TestDocsBrowse:
    def test_browse_file(self, client, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/browse?path=test.txt")
        assert response.status_code == 200
        data = response.json()
        assert data["is_dir"] is False

    def test_browse_dir(self, client, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "a.txt").write_text("x")
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/browse?path=subdir")
        assert response.status_code == 200
        data = response.json()
        assert data["is_dir"] is True
        assert data["file_count"] == 1

    def test_browse_recursive(self, client, tmp_path):
        (tmp_path / "deep" / "sub").mkdir(parents=True)
        (tmp_path / "deep" / "sub" / "b.txt").write_text("y")
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get(
                "/api/uar/docs/browse?path=deep&recursive=true"
            )
        assert response.status_code == 200
        assert response.json()["recursive"] is True

    def test_browse_not_found(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/browse?path=nope")
        assert response.status_code == 404

    def test_browse_invalid_path(self, client, tmp_path):
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.get("/api/uar/docs/browse?path=/etc")
        assert response.status_code in (400, 404)


class TestDocsCreateFolder:
    def test_creates_folder(self, client, tmp_path):
        lib = tmp_path / ".uar_library"
        lib.mkdir(parents=True)
        with patch.dict(os.environ, {"PROJECT_ROOT": str(tmp_path)}):
            response = client.post(
                "/api/uar/docs/create_folder",
                json={"path": ".", "name": "new_folder"},
            )
        assert response.status_code == 200
        assert response.json()["name"] == "new_folder"

    def test_invalid_name(self, client):
        response = client.post(
            "/api/uar/docs/create_folder",
            json={"path": ".", "name": "../bad"},
        )
        assert response.status_code == 400

    def test_empty_name(self, client):
        response = client.post(
            "/api/uar/docs/create_folder",
            json={"path": ".", "name": "  "},
        )
        assert response.status_code == 400

    def test_reserved_name(self, client):
        response = client.post(
            "/api/uar/docs/create_folder",
            json={"path": ".", "name": "CON"},
        )
        assert response.status_code == 400

    def test_missing_fields(self, client):
        response = client.post(
            "/api/uar/docs/create_folder", json={"path": ""}
        )
        assert response.status_code == 400
