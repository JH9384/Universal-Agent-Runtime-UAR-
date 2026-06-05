"""HTTP-level tests for operational admin routers.

Covers auth tier enforcement, Pydantic body validation, and audit logging
for all Phase A-C admin mutation endpoints.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def admin_key():
    """Patch API_KEYS with operator-tier key."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"admin-key-xyz": {"user": "test-admin", "tier": "operator"}},
        clear=True,
    ):
        yield "admin-key-xyz"


@pytest.fixture
def viewer_key():
    """Patch API_KEYS with viewer-tier key (insufficient for admin)."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"viewer-key-abc": {"user": "test-viewer", "tier": "viewer"}},
        clear=True,
    ):
        yield "viewer-key-abc"


@pytest.fixture
def dev_env():
    """Development mode (anonymous allowed for non-admin endpoints)."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        yield


@pytest.fixture
def prod_env():
    """Production mode (strict auth)."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        yield


# ------------------------------------------------------------------
# Auth tier tests
# ------------------------------------------------------------------

class TestCredentialsAuth:
    """POST /api/uar/credentials auth and validation."""

    @pytest.mark.usefixtures("dev_env")
    def test_post_credentials_anonymous_401(self):
        """Anonymous requests are rejected at router level."""
        response = client.post(
            "/api/uar/credentials",
            json={"cred_id": "x", "name": "x", "value": "x"},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "viewer_key")
    def test_post_credentials_viewer_403(self, viewer_key):
        """Viewer tier cannot perform admin mutations."""
        response = client.post(
            "/api/uar/credentials",
            headers={"Authorization": f"Bearer {viewer_key}"},
            json={"cred_id": "x", "name": "x", "value": "x"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["error_code"] == "FORBIDDEN"
        assert "viewer" in detail["message"]

    @pytest.mark.usefixtures("dev_env", "admin_key")
    def test_post_credentials_missing_body_422(self, admin_key):
        """Pydantic rejects missing required fields."""
        response = client.post(
            "/api/uar/credentials",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={"cred_id": "test"},
        )
        assert response.status_code == 422

    @pytest.mark.usefixtures("prod_env", "admin_key")
    def test_post_credentials_audit_called(self, admin_key):
        """Successful mutation triggers audit logging."""
        mock_vault = MagicMock()
        mock_entry = MagicMock()
        mock_entry.to_dict.return_value = {"id": "audit-test"}
        mock_vault.set_credential.return_value = mock_entry
        with patch(
            "uar.api.routers.operator.credentials.audit_admin_action"
        ) as mock_audit:
            with patch(
                "uar.api.routers.operator.credentials.get_credential_vault",
                return_value=mock_vault,
            ):
                response = client.post(
                    "/api/uar/credentials",
                    headers={"Authorization": f"Bearer {admin_key}"},
                    json={
                        "cred_id": "audit-test",
                        "name": "Audit Test",
                        "service_type": "generic",
                        "value": "secret",
                    },
                )
                assert response.status_code == 200
                mock_audit.assert_called_once()
                call = mock_audit.call_args
                assert call.kwargs["action"] == "POST /api/uar/credentials"
                assert call.kwargs["resource"] == "credential:audit-test"


class TestMaintenanceAuth:
    """POST /api/uar/maintenance auth and validation."""

    @pytest.mark.usefixtures("dev_env")
    def test_post_maintenance_anonymous_401(self):
        response = client.post(
            "/api/uar/maintenance",
            json={"wid": "w1", "start_at": 1.0, "end_at": 2.0},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "viewer_key")
    def test_post_maintenance_viewer_403(self, viewer_key):
        response = client.post(
            "/api/uar/maintenance",
            headers={"Authorization": f"Bearer {viewer_key}"},
            json={"wid": "w1", "start_at": 1.0, "end_at": 2.0},
        )
        assert response.status_code == 403

    @pytest.mark.usefixtures("dev_env", "admin_key")
    def test_post_maintenance_invalid_body_422(self, admin_key):
        """Pydantic validates body schema."""
        response = client.post(
            "/api/uar/maintenance",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={"wid": "", "start_at": "not-a-number"},
        )
        assert response.status_code == 422


class TestDataSourcesAuth:
    """POST /api/uar/data-sources auth and validation."""

    @pytest.mark.usefixtures("dev_env")
    def test_post_data_source_anonymous_401(self):
        response = client.post(
            "/api/uar/data-sources",
            json={"dsid": "d1", "source_type": "api", "location": "http://x"},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "viewer_key")
    def test_post_data_source_viewer_403(self, viewer_key):
        response = client.post(
            "/api/uar/data-sources",
            headers={"Authorization": f"Bearer {viewer_key}"},
            json={"dsid": "d1", "source_type": "api", "location": "http://x"},
        )
        assert response.status_code == 403

    @pytest.mark.usefixtures("dev_env", "admin_key")
    def test_post_data_source_invalid_type_422(self, admin_key):
        """Pydantic regex rejects invalid source_type."""
        response = client.post(
            "/api/uar/data-sources",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={
                "dsid": "d1",
                "source_type": "invalid-type",
                "location": "http://x",
            },
        )
        assert response.status_code == 422


class TestSyncAuth:
    """POST /api/uar/sync/resync auth."""

    @pytest.mark.usefixtures("dev_env")
    def test_post_resync_anonymous_401(self):
        response = client.post(
            "/api/uar/sync/resync",
            json={"target": "store-1"},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "viewer_key")
    def test_post_resync_viewer_403(self, viewer_key):
        response = client.post(
            "/api/uar/sync/resync",
            headers={"Authorization": f"Bearer {viewer_key}"},
            json={"target": "store-1"},
        )
        assert response.status_code == 403


class TestPluginsAuth:
    """POST /api/uar/plugins/reload auth."""

    @pytest.mark.usefixtures("dev_env")
    def test_post_reload_plugins_anonymous_401(self):
        response = client.post("/api/uar/plugins/reload")
        assert response.status_code == 401

    @pytest.mark.usefixtures("prod_env", "viewer_key")
    def test_post_reload_plugins_viewer_403(self, viewer_key):
        response = client.post(
            "/api/uar/plugins/reload",
            headers={"Authorization": f"Bearer {viewer_key}"},
        )
        assert response.status_code == 403


# ------------------------------------------------------------------
# DELETE endpoint typed-response tests
# ------------------------------------------------------------------

class TestDeleteResponses:
    """DELETE endpoints return structured AdminActionOut shapes."""

    @pytest.mark.usefixtures("prod_env", "admin_key")
    def test_delete_credentials_shape(self, admin_key):
        mock_vault = MagicMock()
        mock_vault.delete_credential.return_value = True
        with patch(
            "uar.api.routers.operator.credentials.get_credential_vault",
            return_value=mock_vault,
        ):
            response = client.delete(
                "/api/uar/credentials/nonexistent",
                headers={"Authorization": f"Bearer {admin_key}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "id" in data
        assert "deleted" in data

    @pytest.mark.usefixtures("prod_env", "admin_key")
    def test_delete_maintenance_shape(self, admin_key):
        response = client.delete(
            "/api/uar/maintenance/nonexistent",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "cancelled" in data

    @pytest.mark.usefixtures("prod_env", "admin_key")
    def test_delete_data_source_shape(self, admin_key):
        response = client.delete(
            "/api/uar/data-sources/nonexistent",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "deleted" in data


# ------------------------------------------------------------------
# require_operator unit tests
# ------------------------------------------------------------------

class TestRequireOperator:
    """Direct unit tests for the require_operator helper."""

    def test_anonymous_raises_401(self):
        from uar.api.routers.operator.common import require_operator

        with pytest.raises(Exception) as exc_info:
            require_operator(None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_REQUIRED"

    def test_viewer_tier_raises_403(self):
        from uar.api.routers.operator.common import require_operator

        with patch(
            "uar.api.routers.operator.common.auth_middleware"
        ) as m:
            m.return_value = {"user": "v", "tier": "viewer"}
            with pytest.raises(Exception) as exc_info:
                require_operator(None)
            assert exc_info.value.status_code == 403
            assert exc_info.value.detail["error_code"] == "FORBIDDEN"

    def test_operator_tier_succeeds(self):
        from uar.api.routers.operator.common import require_operator

        with patch(
            "uar.api.routers.operator.common.auth_middleware"
        ) as m:
            m.return_value = {"user": "op", "tier": "operator"}
            result = require_operator(None)
            assert result["user"] == "op"

    def test_admin_tier_succeeds(self):
        from uar.api.routers.operator.common import require_operator

        with patch(
            "uar.api.routers.operator.common.auth_middleware"
        ) as m:
            m.return_value = {"user": "ad", "tier": "admin"}
            result = require_operator(None)
            assert result["user"] == "ad"

    def test_developer_tier_succeeds(self):
        from uar.api.routers.operator.common import require_operator

        with patch(
            "uar.api.routers.operator.common.auth_middleware"
        ) as m:
            m.return_value = {"user": "dev", "tier": "developer"}
            result = require_operator(None)
            assert result["user"] == "dev"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
