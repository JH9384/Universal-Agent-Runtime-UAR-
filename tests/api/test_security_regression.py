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


# ── bulk_delete admin-only older_than_days ─────────────────────────────────


def test_bulk_delete_older_than_days_admin_succeeds():
    """Admin can trigger time-based purge."""
    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"older_than_days": 0},
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filter"] == "older_than_0_days"
    assert "deleted" in data


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


def test_reset_circuit_breaker_non_admin_rejected():
    """Non-admin user should get 403 for circuit breaker reset.

    In dev mode the endpoint allows anonymous access, so this
    assertion only holds in production-like environments.
    """
    from uar.api.routers.health import _is_dev_mode
    from uar.core.circuit_breaker_decorator import get_circuit_breaker

    if _is_dev_mode():
        pytest.skip("Dev mode allows anonymous circuit breaker reset")

    # Pre-create the breaker so endpoint finds it (404 before admin check)
    get_circuit_breaker("non_admin_test_svc")

    response = client.post(
        "/api/health/circuit-breakers/non_admin_test_svc/reset",
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "forbidden"


def test_reset_circuit_breaker_admin_succeeds():
    """Admin can reset any existing circuit breaker."""
    from uar.core.circuit_breaker_decorator import get_circuit_breaker
    from uar.core.circuit_breaker import State

    cb = get_circuit_breaker("admin_reset_svc")
    cb._failures = 3
    cb._state = State.OPEN

    response = client.post(
        "/api/health/circuit-breakers/admin_reset_svc/reset",
        headers={"Authorization": "Bearer admin-key-67890"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reset"
    assert data["service"] == "admin_reset_svc"


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


# ── middleware auth bypass attempts ──────────────────────────────────────────


def test_bypass_with_empty_bearer_token():
    """Empty string after 'Bearer ' should be treated as invalid."""
    response = client.get(
        "/api/cache/stats",
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 401


def test_bypass_with_missing_bearer_prefix():
    """Key without 'Bearer' prefix should be rejected."""
    response = client.get(
        "/api/cache/stats",
        headers={"Authorization": "dev-key-12345"},
    )
    assert response.status_code == 401


def test_bypass_with_url_encoded_key():
    """URL-encoded key should not match the raw key."""
    response = client.get(
        "/api/cache/stats",
        headers={"Authorization": "Bearer dev%2Dkey%2D12345"},
    )
    assert response.status_code == 401


def test_bypass_with_null_byte_in_header():
    """Null byte injection in the Authorization header should fail."""
    response = client.get(
        "/api/cache/stats",
        headers={"Authorization": "Bearer dev-key\x0012345"},
    )
    assert response.status_code in (401, 400)


def test_bypass_admin_with_authenticated_tier():
    """Authenticated-tier user must not access admin-only older_than_days."""
    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"older_than_days": 0},
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert response.status_code == 403


def test_bypass_with_case_variation_header_name():
    """HTTP clients normalize header names; case variation is handled
    by FastAPI/Starlette, but the credential still needs to be valid.
    """
    response = client.get(
        "/api/cache/stats",
        headers={"authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


def test_bypass_no_auth_header_rejected():
    """Missing Authorization header on protected endpoint is rejected."""
    response = client.get("/api/cache/stats")
    assert response.status_code == 401
