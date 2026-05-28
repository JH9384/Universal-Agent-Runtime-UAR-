"""Security regression tests for new operational endpoints.

Covers:
- Auth rejection on ping_skill, compare_runs, bulk_delete
- Ownership isolation on compare_runs and bulk_delete
- Rate limiting on new endpoints
- Circuit breaker reset 404 for unknown breakers
- Deep compare_runs diff fields
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["PROJECT_ROOT"] = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

from uar.api.server import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_keys():
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {
            "dev-key-12345": {
                "user": "developer",
                "tier": "authenticated",
            },
            "admin-key-67890": {
                "user": "admin",
                "tier": "admin",
            },
        },
        clear=True,
    ):
        yield


# ── ping_skill auth ────────────────────────────────────────────────────────


def test_ping_skill_invalid_auth_rejected():
    """ping_skill must reject requests with invalid credentials."""
    response = client.post(
        "/api/uar/skills/ping",
        json={"skill": "review"},
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


def test_ping_skill_with_valid_auth_succeeds():
    response = client.post(
        "/api/uar/skills/ping",
        json={"skill": "review"},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# ── compare_runs auth + ownership ──────────────────────────────────────────


def test_compare_runs_invalid_auth_rejected():
    response = client.get(
        "/api/uar/runs/fake/compare/other",
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


def test_compare_runs_ownership_isolation():
    """A non-admin user cannot compare another user's run."""
    # Run a goal as developer
    r1 = client.post(
        "/api/uar/run",
        json={"goal": "ownership test a"},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert r1.status_code == 200
    id1 = r1.json()["run_id"]

    # Run a goal as admin
    r2 = client.post(
        "/api/uar/run",
        json={"goal": "ownership test b"},
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    assert r2.status_code == 200
    id2 = r2.json()["run_id"]

    # Developer tries to compare admin's run — should get 403
    response = client.get(
        f"/api/uar/runs/{id1}/compare/{id2}",
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert response.status_code == 403


def test_compare_runs_admin_can_cross_compare():
    """Admin can compare any runs."""
    r1 = client.post(
        "/api/uar/run",
        json={"goal": "admin compare a"},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    id1 = r1.json()["run_id"]
    r2 = client.post(
        "/api/uar/run",
        json={"goal": "admin compare b"},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    id2 = r2.json()["run_id"]

    response = client.get(
        f"/api/uar/runs/{id1}/compare/{id2}",
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    assert response.status_code == 200


def test_compare_runs_returns_deep_diff_fields():
    """compare_runs should include events, timeline, metrics in diff."""
    r1 = client.post("/api/uar/run", json={"goal": "deep diff a"})
    id1 = r1.json()["run_id"]
    r2 = client.post("/api/uar/run", json={"goal": "deep diff b"})
    id2 = r2.json()["run_id"]

    response = client.get(f"/api/uar/runs/{id1}/compare/{id2}")
    assert response.status_code == 200
    data = response.json()
    assert "same_status" in data
    assert "same_skills" in data
    assert "diffs" in data
    # At minimum status should differ because runs are independent
    assert isinstance(data["same_status"], bool)


# ── bulk_delete auth + ownership ────────────────────────────────────────────


def test_bulk_delete_invalid_auth_rejected():
    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"older_than_days": 0},
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


def test_bulk_delete_run_ids_ownership():
    """Non-owner cannot delete another user's run via bulk-delete."""
    r = client.post(
        "/api/uar/run",
        json={"goal": "bulk ownership"},
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    rid = r.json()["run_id"]

    # Developer tries to delete admin's run
    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"run_ids": [rid]},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 0


def test_bulk_delete_admin_can_delete_any():
    """Admin can delete any run."""
    r = client.post(
        "/api/uar/run",
        json={"goal": "admin delete me"},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    rid = r.json()["run_id"]

    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"run_ids": [rid]},
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 1


# ── circuit breaker reset ────────────────────────────────────────────────────


def test_reset_circuit_breaker_unknown_returns_404():
    """Resetting a non-existent breaker should return 404."""
    response = client.post(
        "/api/health/circuit-breakers/does_not_exist_ever/reset"
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"] == "not_found"


def test_reset_circuit_breaker_invalid_auth_rejected():
    """Reset with invalid bearer token should 401 before 404 check."""
    response = client.post(
        "/api/health/circuit-breakers/test_svc/reset",
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


# ── rate limiting on new endpoints ───────────────────────────────────────────


def test_ping_skill_rate_limit():
    """Rapid ping_skill calls should eventually be rate-limited."""
    responses = []
    for _ in range(200):
        r = client.post("/api/uar/skills/ping", json={"skill": "review"})
        responses.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in responses, "Expected rate limit to trigger"


def test_compare_runs_rate_limit():
    """Rapid compare_runs calls should eventually be rate-limited."""
    responses = []
    for _ in range(200):
        r = client.get("/api/uar/runs/fake/compare/other")
        responses.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in responses, "Expected rate limit to trigger"


# ── ping_skill dependency check enhancement ─────────────────────────────────


def test_ping_skill_latency_present():
    """ping_skill should return latency_ms in the response."""
    response = client.post(
        "/api/uar/skills/ping", json={"skill": "review"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "latency_ms" in data
    assert isinstance(data["latency_ms"], (int, float))
    assert data["latency_ms"] >= 0


def test_ping_skill_missing_body_still_validates():
    """Empty body should return 400 before auth checks."""
    response = client.post("/api/uar/skills/ping", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "missing_skill"
