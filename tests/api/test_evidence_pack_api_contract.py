"""D5U active Evidence Pack API contract tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.evidence_pack import router


AUTH_HEADERS = {"Authorization": "Bearer dev-key-12345"}


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEYS", "dev-key-12345:test-user:admin")
    monkeypatch.setenv("UAR_AUTH_MODE", "api_key")

    import uar.api.middleware as middleware

    middleware.API_KEYS = {
        "dev-key-12345": {"user": "test-user", "tier": "admin"}
    }

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_evidence_pack_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/uar/evidence-pack/run-123")

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "authentication_required"


def test_evidence_pack_endpoint_returns_contract_shape(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/uar/evidence-pack/run-123", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["run_id"] == "run-123"
    assert "evidence_pack" in payload
    assert "markdown" in payload

    pack = payload["evidence_pack"]
    assert pack["evidence_pack_id"] == "evidence-pack:run-123"
    assert pack["run_id"] == "run-123"

    for section in (
        "signal",
        "mission_control",
        "replay",
        "burnin",
        "certification",
        "trust",
        "outcome",
        "closure",
    ):
        assert section in pack
        assert set(pack[section]) == {"available", "source", "data", "missing"}


def test_evidence_pack_endpoint_includes_markdown_when_requested(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_markdown": "true"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload["markdown"], str)
    assert "Evidence Pack v2" in payload["markdown"]
    assert "run-123" in payload["markdown"]


def test_evidence_pack_endpoint_keeps_missing_sections_explicit(monkeypatch):
    client = _client(monkeypatch)

    response = client.get(
        "/api/uar/evidence-pack/run-missing-sections",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    pack = response.json()["evidence_pack"]

    assert pack["replay"]["available"] is False
    assert pack["replay"]["data"] is None
    assert pack["replay"]["missing"]


def test_evidence_pack_endpoint_rejects_empty_run_id(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/uar/evidence-pack/%20", headers=AUTH_HEADERS)

    assert response.status_code == 422


def test_evidence_pack_endpoint_is_read_only(monkeypatch, tmp_path):
    client = _client(monkeypatch)

    before_reports_exists = tmp_path.joinpath("reports").exists()

    response = client.get("/api/uar/evidence-pack/run-123", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert "outcome_created" not in payload
    assert "trust_updated" not in payload
    assert "artifact_promoted" not in payload
    assert before_reports_exists is False
