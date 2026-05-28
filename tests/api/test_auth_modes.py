"""Auth mode tests: verify local dev (anonymous-friendly) vs shared (strict)
behavior.

Endpoints must allow anonymous access in development for read-only operations
while keeping auth requirements strict in production/shared deployments.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


@pytest.fixture
def dev_env():
    """Patch ENVIRONMENT to development."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        yield


@pytest.fixture
def prod_env():
    """Patch ENVIRONMENT to production."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        yield


@pytest.fixture
def api_keys():
    """Patch API_KEYS for authenticated requests."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


class TestDocsReadOnlyAnonymous:
    """Read-only docs endpoints should allow anonymous in dev."""

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_presets_anonymous_dev(self):
        """GET /api/uar/docs/presets allows anonymous in dev."""
        response = client.get("/api/uar/docs/presets")
        assert response.status_code == 200
        data = response.json()
        assert "project_root" in data
        assert "presets" in data

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_library_list_anonymous_dev(self):
        """GET /api/uar/docs/library allows anonymous in dev."""
        response = client.get("/api/uar/docs/library")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_browse_anonymous_dev(self):
        """GET /api/uar/docs/browse allows anonymous in dev."""
        response = client.get("/api/uar/docs/browse?path=.")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_browse_recursive_anonymous_dev(self):
        """GET /api/uar/docs/browse?recursive=true allows anonymous in dev."""
        response = client.get("/api/uar/docs/browse?path=.&recursive=true")
        assert response.status_code == 200


class TestDocsReadOnlyAuth:
    """Read-only docs endpoints should still work with auth in dev."""

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_browse_authenticated_dev(self):
        """GET /api/uar/docs/browse works with auth in dev."""
        response = client.get(
            "/api/uar/docs/browse?path=.",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert response.status_code == 200


class TestDocsReadOnlyProduction:
    """Read-only docs endpoints require auth in production."""

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_docs_presets_requires_auth_prod(self):
        """GET /api/uar/docs/presets returns 401 without auth in prod."""
        response = client.get("/api/uar/docs/presets")
        assert response.status_code == 401
        assert "unauthorized" in response.json()["detail"]["error"]

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_docs_library_list_requires_auth_prod(self):
        """GET /api/uar/docs/library returns 401 without auth in prod."""
        response = client.get("/api/uar/docs/library")
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_docs_browse_requires_auth_prod(self):
        """GET /api/uar/docs/browse returns 401 without auth in prod."""
        response = client.get("/api/uar/docs/browse?path=.")
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["error"] == "unauthorized"
        assert "module" in detail
        assert detail["module"] == "uar.api.routers.docs"

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_docs_read_only_work_with_auth_prod(self):
        """Read-only docs endpoints succeed with valid auth in prod."""
        headers = {"Authorization": "Bearer dev-key-12345"}
        assert (
            client.get("/api/uar/docs/presets", headers=headers).status_code
            == 200
        )
        assert (
            client.get("/api/uar/docs/library", headers=headers).status_code
            == 200
        )
        assert (
            client.get(
                "/api/uar/docs/browse?path=.", headers=headers
            ).status_code
            == 200
        )


class TestDocsWriteAlwaysRequiresAuth:
    """Write endpoints must require auth regardless of environment."""

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_upload_requires_auth_dev(self):
        """POST /api/uar/docs/upload requires auth even in dev."""
        response = client.post(
            "/api/uar/docs/upload",
            files={"files": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_library_delete_requires_auth_dev(self):
        """DELETE /api/uar/docs/library requires auth even in dev."""
        response = client.delete("/api/uar/docs/library?name=test.txt")
        assert response.status_code == 401

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_docs_create_folder_requires_auth_dev(self):
        """POST /api/uar/docs/create_folder requires auth even in dev."""
        response = client.post(
            "/api/uar/docs/create_folder", json={"path": "test"}
        )
        assert response.status_code == 401


class TestHealthCircuitBreakers:
    """Circuit breaker health endpoint auth behavior."""

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_circuit_breakers_anonymous_dev(self):
        """GET /api/health/circuit-breakers allows anonymous in dev."""
        response = client.get("/api/health/circuit-breakers")
        # 200 = healthy, 503 = degraded (open circuits); both != 401
        assert response.status_code in (200, 503)
        data = response.json()
        assert "circuits" in data

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_circuit_breakers_requires_auth_prod(self):
        """GET /api/health/circuit-breakers returns 401 without auth
        in prod."""
        response = client.get("/api/health/circuit-breakers")
        assert response.status_code == 401
        assert "unauthorized" in response.json()["detail"]["error"]

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_circuit_breakers_with_auth_prod(self):
        """GET /api/health/circuit-breakers succeeds with auth in prod."""
        response = client.get(
            "/api/health/circuit-breakers",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        # 200 = healthy, 503 = degraded (open circuits); both != 401
        assert response.status_code in (200, 503)


class TestHealthOpenEndpoints:
    """Health endpoints that should remain open in all environments."""

    def test_health_check_no_auth(self):
        """GET /api/health is always open."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_liveness_no_auth(self):
        """GET /api/health/live is always open."""
        response = client.get("/api/health/live")
        assert response.status_code == 200

    def test_readiness_no_auth(self):
        """GET /api/health/ready is always open."""
        response = client.get("/api/health/ready")
        assert response.status_code == 200

    @pytest.mark.usefixtures("api_keys")
    def test_status_no_auth(self):
        """GET /api/status allows anonymous (labels user as 'anonymous')."""
        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.json()["user"] == "anonymous"

    @pytest.mark.usefixtures("api_keys")
    def test_dashboard_no_auth(self):
        """GET /api/health/dashboard is always open."""
        response = client.get("/api/health/dashboard")
        assert response.status_code == 200
        assert "skills" in response.json()


class TestAuthMiddlewareSpecificity:
    """Verify auth error responses include module/function specificity."""

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_docs_browse_error_includes_module(self):
        """401 from docs_browse includes endpoint and module fields."""
        response = client.get("/api/uar/docs/browse?path=.")
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["module"] == "uar.api.routers.docs"
        assert "endpoint" in detail
        assert "docs_browse" in detail["message"]

    @pytest.mark.usefixtures("prod_env", "api_keys")
    def test_invalid_key_includes_module(self):
        """401 for invalid API key includes module and function fields."""
        response = client.get(
            "/api/uar/docs/browse?path=.",
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["module"] == "uar.api.middleware"
        assert detail["function"] == "auth_middleware"
        assert detail["error_code"] == "INVALID_API_KEY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
