"""D5R Evidence Pack API contract tests.

These tests are intentionally skipped until D5S wires the read-only router.
They preserve the D5Q contract before implementation begins.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.skip(
    reason="D5R contract scaffold only; enable during D5S router implementation"
)


def test_evidence_pack_endpoint_requires_auth(client):
    response = client.get("/api/uar/evidence-pack/run-123")

    assert response.status_code == 401


def test_evidence_pack_endpoint_returns_contract_shape(auth_client):
    response = auth_client.get("/api/uar/evidence-pack/run-123")

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


def test_evidence_pack_endpoint_includes_markdown_when_requested(auth_client):
    response = auth_client.get(
        "/api/uar/evidence-pack/run-123",
        params={"include_markdown": "true"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload["markdown"], str)
    assert "Evidence Pack v2" in payload["markdown"]


def test_evidence_pack_endpoint_keeps_missing_sections_explicit(auth_client):
    response = auth_client.get("/api/uar/evidence-pack/run-missing-sections")

    assert response.status_code == 200
    pack = response.json()["evidence_pack"]

    assert pack["replay"]["available"] is False
    assert pack["replay"]["data"] is None
    assert pack["replay"]["missing"]


def test_evidence_pack_endpoint_rejects_empty_run_id(auth_client):
    response = auth_client.get("/api/uar/evidence-pack/%20")

    assert response.status_code == 422


def test_evidence_pack_endpoint_is_read_only(auth_client):
    response = auth_client.get("/api/uar/evidence-pack/run-123")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert "outcome_created" not in payload
    assert "trust_updated" not in payload
    assert "artifact_promoted" not in payload
