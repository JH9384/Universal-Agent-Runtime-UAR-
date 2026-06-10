from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.evidence_pack import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_evidence_pack_router_returns_minimal_pack():
    client = _client()

    response = client.get("/api/uar/evidence-pack/run-123")

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


def test_evidence_pack_router_includes_markdown_when_requested():
    client = _client()

    response = client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_markdown": "true"},
    )

    assert response.status_code == 200
    markdown = response.json()["markdown"]

    assert isinstance(markdown, str)
    assert "Evidence Pack v2" in markdown
    assert "run-123" in markdown


def test_evidence_pack_router_rejects_empty_run_id():
    client = _client()

    response = client.get("/api/uar/evidence-pack/%20")

    assert response.status_code == 422


def test_evidence_pack_router_can_hide_unavailable_sections():
    client = _client()

    response = client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_unavailable": "false"},
    )

    assert response.status_code == 200
    pack = response.json()["evidence_pack"]

    assert "mission_control" not in pack
    assert "burnin" not in pack
    assert "certification" not in pack
