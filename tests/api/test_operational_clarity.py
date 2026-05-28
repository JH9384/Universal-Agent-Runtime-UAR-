"""Tests for operational clarity features:

- Lifespan validation fail-fast
- Skill ping endpoint
- Circuit breaker reset endpoint
- Run comparison endpoint
- Bulk delete endpoint
- Deprecated CLI warning
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure PROJECT_ROOT points to a writable directory before importing
# modules that eagerly create recipe service files.
os.environ["PROJECT_ROOT"] = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

from fastapi.testclient import TestClient  # noqa: E402

from uar.api.server import app  # noqa: E402
from uar.core.circuit_breaker_decorator import (  # noqa: E402
    get_circuit_breaker,
    reset_circuit_breaker,
)
from uar.core.circuit_breaker import State  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_keys():
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


# ── Lifespan validation ────────────────────────────────────────────────────


def test_lifespan_raises_on_validation_failure():
    """Startup should fail fast when validate_environment returns issues."""
    with patch(
        "uar.config.validate_environment",
        return_value=["Fake validation error"],
    ), patch(
        "uar.config.validate_docker_environment", return_value=[]
    ), pytest.raises(
        RuntimeError, match="UAR startup validation failed"
    ):
        from uar.api.lifespan import create_lifespan
        from fastapi import FastAPI

        app = FastAPI()
        cm = create_lifespan(MagicMock())(app)
        import asyncio

        asyncio.run(cm.__aenter__())


# ── Skill ping endpoint ─────────────────────────────────────────────────────


def test_ping_skill_ok():
    response = client.post("/api/uar/skills/ping", json={"skill": "review"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["skill"] == "review"
    assert "latency_ms" in data


def test_ping_skill_missing_body():
    response = client.post("/api/uar/skills/ping", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "missing_skill"


def test_ping_skill_not_found():
    response = client.post(
        "/api/uar/skills/ping", json={"skill": "does_not_exist_ever"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "skill_not_found"


# ── Circuit breaker reset endpoint ───────────────────────────────────────────


def test_reset_circuit_breaker():
    cb = get_circuit_breaker("test_svc")
    cb._failures = 5
    cb._state = State.OPEN

    response = client.post("/api/health/circuit-breakers/test_svc/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reset"
    assert data["service"] == "test_svc"

    reset_circuit_breaker("test_svc")


# ── Run comparison endpoint ─────────────────────────────────────────────────


def test_compare_runs():
    # Run two goals to get run IDs
    r1 = client.post("/api/uar/run", json={"goal": "test a"})
    assert r1.status_code == 200
    id1 = r1.json()["run_id"]

    r2 = client.post("/api/uar/run", json={"goal": "test b"})
    assert r2.status_code == 200
    id2 = r2.json()["run_id"]

    response = client.get(f"/api/uar/runs/{id1}/compare/{id2}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_a"] == id1
    assert data["run_b"] == id2
    assert isinstance(data["same_status"], bool)
    assert isinstance(data["same_skills"], bool)
    assert "diffs" in data


def test_compare_runs_not_found():
    response = client.get("/api/uar/runs/bad-id/compare/other-bad-id")
    assert response.status_code == 404


# ── Bulk delete endpoint ────────────────────────────────────────────────────


def test_bulk_delete_by_run_ids():
    r = client.post("/api/uar/run", json={"goal": "bulk delete me"})
    assert r.status_code == 200
    rid = r.json()["run_id"]

    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"run_ids": [rid]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] >= 0
    assert data["filter"] == "run_ids"


def test_bulk_delete_by_older_than_days_requires_admin():
    response = client.post(
        "/api/uar/runs/bulk-delete",
        json={"older_than_days": 0},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "forbidden"


def test_bulk_delete_missing_filter():
    response = client.post("/api/uar/runs/bulk-delete", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "missing_filter"


# ── Deprecated CLI ───────────────────────────────────────────────────────────


def test_run_py_deprecation_warning():
    import warnings

    from uar.cli.run import main

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            main()
        except SystemExit:
            pass

        dep_warns = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(dep_warns) >= 1


# ── Doctor CLI helpers ───────────────────────────────────────────────────────


def test_validate_environment_returns_list():
    from uar.config import validate_environment

    issues = validate_environment()
    assert isinstance(issues, list)


def test_validate_docker_environment_returns_list():
    from uar.config import validate_docker_environment

    issues = validate_docker_environment()
    assert isinstance(issues, list)


def test_advanced_config_validation():
    from uar.config_advanced import validate_advanced_config

    result = validate_advanced_config()
    assert "valid" in result
    assert "issues" in result
    assert "warnings" in result
