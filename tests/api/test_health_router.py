"""Tests for uar.api.routers.health.

Covers health probes, circuit breaker inspection, dashboard, and
circuit breaker reset endpoints.
"""

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


def _reset_all_circuit_breakers():
    """Clear global circuit breaker state between tests."""
    from uar.core.circuit_breaker_decorator import (
        _circuit_breakers,
        reset_circuit_breaker,
    )
    for name in list(_circuit_breakers.keys()):
        asyncio.run(reset_circuit_breaker(name))


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up test API keys for authenticated endpoints."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "admin"}},
        clear=True,
    ):
        yield


class TestHealthCheck:
    def test_health_returns_version(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uor_upstream_version" in data


class TestLivenessProbe:
    def test_live(self):
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "alive"


class TestReadinessProbe:
    def test_ready(self):
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "ready"
        assert data["checks"]["disk_writable"] is True


class TestCircuitBreakers:
    def test_list_circuit_breakers_authenticated(self):
        _reset_all_circuit_breakers()
        response = client.get(
            "/api/health/circuit-breakers",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "circuits" in data
        assert "status" in data

    def test_list_circuit_breakers_with_open(self):
        _reset_all_circuit_breakers()
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker,
        )

        cb = get_circuit_breaker("test_open_svc", failure_threshold=1)

        def _fail():
            raise RuntimeError("fail")

        try:
            cb.call(_fail)
        except Exception:
            pass

        response = client.get(
            "/api/health/circuit-breakers",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 503
        data = response.json()["data"]
        assert data["status"] == "degraded"

    def test_reset_circuit_breaker(self):
        _reset_all_circuit_breakers()
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker,
            get_circuit_breaker_states,
        )

        cb = get_circuit_breaker("test_reset_svc", failure_threshold=1)

        def _fail():
            raise RuntimeError("fail")

        try:
            cb.call(_fail)
        except Exception:
            pass

        states = asyncio.run(get_circuit_breaker_states())
        assert states["test_reset_svc"] == "open"

        response = client.post(
            "/api/health/circuit-breakers/test_reset_svc/reset",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "reset"
        states = asyncio.run(get_circuit_breaker_states())
        assert states["test_reset_svc"] == "closed"

    def test_reset_unknown_breaker(self):
        response = client.post(
            "/api/health/circuit-breakers/nonexistent/reset",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 404

    def test_circuit_breakers_returns_rich_details(self):
        _reset_all_circuit_breakers()
        from uar.core.circuit_breaker_decorator import get_circuit_breaker

        cb = get_circuit_breaker("rich_detail_svc", failure_threshold=1)

        def _fail():
            raise RuntimeError("fail")

        try:
            cb.call(_fail)
        except Exception:
            pass

        response = client.get(
            "/api/health/circuit-breakers",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 503
        data = response.json()["data"]
        circuit = data["circuits"]["rich_detail_svc"]
        assert circuit["state"] == "open"
        assert circuit["failures"] == 1
        assert "half_open_count" in circuit
        assert "half_open_successes" in circuit
        assert "last_failure_time" in circuit


class TestHealthDashboard:
    def test_dashboard_authenticated(self):
        response = client.get(
            "/api/health/dashboard",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "skills" in data
        assert "circuit_breakers" in data
        assert "server_version" in data
        assert "uptime_seconds" in data

    def test_dashboard_unauthorized_in_production(self):
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            response = client.get("/api/health/dashboard")
            assert response.status_code == 401

    def test_dashboard_circuit_breakers_rich_details(self):
        _reset_all_circuit_breakers()
        from uar.core.circuit_breaker_decorator import get_circuit_breaker

        cb = get_circuit_breaker("dash_detail_svc", failure_threshold=1)

        def _fail():
            raise RuntimeError("fail")

        try:
            cb.call(_fail)
        except Exception:
            pass

        response = client.get(
            "/api/health/dashboard",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        circuit = next(
            (
                c
                for c in data["circuit_breakers"]
                if c["name"] == "dash_detail_svc"
            ),
            None,
        )
        assert circuit is not None
        assert circuit["state"] == "open"
        assert circuit["failures"] == 1
        assert "half_open_count" in circuit
        assert "half_open_successes" in circuit
        assert "last_failure_time" in circuit


class TestReadinessProbeEdgeCases:
    def test_ready_disk_error(self):
        with patch(
            "uar.api.routers.health.os.unlink",
            side_effect=OSError("perm denied"),
        ):
            response = client.get("/api/health/ready")
        assert response.status_code == 503
        assert response.json()["data"]["checks"]["disk_writable"] is False


class TestCircuitBreakerAuth:
    def test_circuit_breakers_unauthorized_in_production(self):
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            response = client.get("/api/health/circuit-breakers")
            assert response.status_code == 401

    def test_reset_unauthorized_in_production(self):
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            response = client.post(
                "/api/health/circuit-breakers/test/reset"
            )
            assert response.status_code == 401

    def test_reset_forbidden_non_admin(self):
        with patch.dict(
            "uar.api.middleware.API_KEYS",
            {"dev-key": {"user": "viewer", "tier": "free"}},
            clear=True,
        ), patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            response = client.post(
                "/api/health/circuit-breakers/test/reset",
                headers={"Authorization": "Bearer dev-key"},
            )
            assert response.status_code == 403


class TestHealthDashboardEdgeCases:
    def test_dashboard_skill_error(self):
        from uar.core.registry import registry
        with patch.object(
            registry, "list", return_value=["bad_skill"],
        ), patch.object(
            registry, "get", side_effect=Exception("skill broken"),
        ):
            response = client.get(
                "/api/health/dashboard",
                headers={"Authorization": "Bearer dev-key-12345"},
            )
        assert response.status_code == 200
        skills = response.json()["data"]["skills"]
        bad = [s for s in skills if s["name"] == "bad_skill"]
        assert bad[0]["available"] is False
