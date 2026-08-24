"""Tests for UOR object binary content upload/download endpoints."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app, require_auth
from uar.objects import get_default_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up and fully restore the shared app's auth override."""
    previous_override = app.dependency_overrides.get(require_auth)
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        # Re-apply dependency override in case another test cleared it
        app.dependency_overrides[require_auth] = lambda: {
            "user": "test",
            "tier": "authenticated",
        }
        yield
        if previous_override is None:
            app.dependency_overrides.pop(require_auth, None)
        else:
            app.dependency_overrides[require_auth] = previous_override


def _create_test_object(unique: str = "") -> str:
    """Create a minimal UOR object and return its digest."""
    from uar.objects import create_record

    store = get_default_store()
    record = create_record(
        store,
        mediaType="application/json",
        mode="immutable",
        attributes={"test": True},
        links=[],
        content={"hello": "world", "unique": unique},
    )
    return record["digest"]


def test_upload_content_for_object():
    """POST /api/uor/objects/{digest}/content stores binary blob."""
    digest = _create_test_object()
    data = b"Hello binary world"
    response = client.post(
        f"/objects/{digest}/content",
        files={
            "file": ("hello.txt", BytesIO(data), "text/plain"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["digest"] == digest
    assert body["media_type"] == "text/plain"
    assert body["size"] == len(data)


def test_download_content():
    """GET /objects/{digest}/download returns stored blob."""
    digest = _create_test_object()
    data = b"Downloadable bytes"
    client.post(
        f"/objects/{digest}/content",
        files={
            "file": ("data.bin", BytesIO(data), "application/octet-stream"),
        },
    )
    response = client.get(f"/objects/{digest}/download")
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "application/octet-stream"
    assert "attachment" in response.headers["content-disposition"]


def test_download_missing_content():
    """Download for object without content returns 404."""
    digest = _create_test_object(unique="missing")
    response = client.get(f"/objects/{digest}/download")
    assert response.status_code == 404
    assert "No content" in response.json()["detail"]


def test_upload_to_missing_object():
    """Upload to non-existent object returns 404."""
    response = client.post(
        "/objects/sha256:deadbeef/content",
        files={
            "file": ("x.txt", BytesIO(b"x"), "text/plain"),
        },
    )
    assert response.status_code == 404
