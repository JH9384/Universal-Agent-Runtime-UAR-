"""Tests for uar.api.routers.health.

Covers health probes, circuit breaker inspection, dashboard, and
circuit breaker reset endpoints.
"""

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
        reset_circuit_breaker(name)


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
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uor_upstream_version" in data


class TestLivenessProbe:
    def test_live(self):
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestReadinessProbe:
    def test_ready(self):
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        data = response.json()
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
        data = response.json()
        assert "circuits" in data
        assert "status" in data

    def test_reset_circuit_breaker(self):
        _reset_all_circuit_breakers()
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker,
            get_circuit_breaker_states,
        )

        cb = get_circuit_breaker("test_reset_svc")
        # Force the circuit open by simulating failures
        cb._state = cb._state.__class__("open")
        cb._last_failure_time = __import__("time").time()
        assert get_circuit_breaker_states()["test_reset_svc"] == "open"

        response = client.post(
            "/api/health/circuit-breakers/test_reset_svc/reset",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "reset"
        assert get_circuit_breaker_states()["test_reset_svc"] == "closed"

    def test_reset_unknown_breaker(self):
        response = client.post(
            "/api/health/circuit-breakers/nonexistent/reset",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 404


class TestHealthDashboard:
    def test_dashboard_authenticated(self):
        response = client.get(
            "/api/health/dashboard",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert "circuit_breakers" in data
        assert "server_version" in data
        assert "uptime_seconds" in data

    def test_dashboard_unauthorized_in_production(self):
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            response = client.get("/api/health/dashboard")
            assert response.status_code == 401
