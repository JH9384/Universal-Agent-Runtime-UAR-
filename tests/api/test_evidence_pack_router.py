from __future__ import annotations


from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.evidence_pack import router


AUTH_HEADERS = {"Authorization": "Bearer dev-key-12345"}


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEYS", "dev-key-12345:test-user:admin")
    monkeypatch.setenv("UAR_AUTH_MODE", "api_key")

    # Some paths load auth keys at import time, so update the
    # module globals used by the dependency for this isolated router test.
    import uar.api.middleware as middleware

    middleware.API_KEYS = {
        "dev-key-12345": {"user": "test-user", "tier": "admin"}
    }

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_evidence_pack_router_requires_auth(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/uar/evidence-pack/run-123")

    assert response.status_code in (401, 403)


def test_evidence_pack_router_returns_minimal_pack(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/uar/evidence-pack/run-123", headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["run_id"] == "run-123"
    assert payload["markdown"] is None

    pack = payload["evidence_pack"]
    assert pack["evidence_pack_id"] == "evidence-pack:run-123"
    assert pack["run_id"] == "run-123"
    assert pack["mission_control"]["available"] is False
    assert pack["burnin"]["available"] is False
    assert pack["certification"]["available"] is False


def test_evidence_pack_router_includes_markdown_when_requested(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_markdown": "true"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    markdown = response.json()["markdown"]

    assert isinstance(markdown, str)
    assert "Evidence Pack v2" in markdown
    assert "run-123" in markdown


def test_evidence_pack_router_rejects_empty_run_id(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/uar/evidence-pack/%20", headers=AUTH_HEADERS)

    assert response.status_code == 422


def test_evidence_pack_router_can_hide_unavailable_sections(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_unavailable": "false"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    pack = response.json()["evidence_pack"]

    assert "mission_control" not in pack
    assert "burnin" not in pack
    assert "certification" not in pack
