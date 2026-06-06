"""Auth-branch coverage for Mission Control router endpoints.

Targets the 401 (unauthenticated) and 403 (insufficient tier) branches
that the coverage report identified as uncovered.
"""

import os
from unittest.mock import patch

import pytest

os.environ["PROJECT_ROOT"] = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

from fastapi.testclient import TestClient  # noqa: E402

from uar.api.server import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Provide authenticated (viewer), operator, and admin keys."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {
            "viewer-key": {"user": "viewer", "tier": "viewer"},
            "operator-key": {"user": "operator", "tier": "operator"},
            "admin-key": {"user": "admin", "tier": "admin"},
        },
        clear=True,
    ):
        yield


# ── bulk_record_outcome (POST /api/uar/recommendations/outcome/bulk) ──


class TestBulkRecordOutcomeAuth:
    def test_401_without_auth(self):
        response = client.post(
            "/api/uar/recommendations/outcome/bulk",
            json={"items": []},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] in (
            "unauthorized", "authentication_required"
        )

    def test_403_viewer_cannot_bulk(self):
        response = client.post(
            "/api/uar/recommendations/outcome/bulk",
            json={"items": []},
            headers={"Authorization": "Bearer viewer-key"},
        )
        assert response.status_code == 403

    def test_403_operator_cannot_bulk(self):
        response = client.post(
            "/api/uar/recommendations/outcome/bulk",
            json={"items": []},
            headers={"Authorization": "Bearer operator-key"},
        )
        assert response.status_code == 403

    def test_400_items_not_a_list(self):
        response = client.post(
            "/api/uar/recommendations/outcome/bulk",
            json={"items": "not-a-list"},
            headers={"Authorization": "Bearer admin-key"},
        )
        assert response.status_code == 400
        assert (
            response.json()["detail"]["error"] == "invalid_items"
        )

    def test_admin_empty_items_ok(self):
        response = client.post(
            "/api/uar/recommendations/outcome/bulk",
            json={"items": []},
            headers={"Authorization": "Bearer admin-key"},
        )
        assert response.status_code == 200
        assert response.json()["recorded"] == 0


# ── get_recommendation_audit (GET /api/uar/recommendations/audit) ──


class TestRecommendationAuditAuth:
    def test_401_without_auth(self):
        response = client.get(
            "/api/uar/recommendations/audit?recommendation_id=r1"
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] in (
            "unauthorized", "authentication_required"
        )

    def test_403_viewer_cannot_audit(self):
        response = client.get(
            "/api/uar/recommendations/audit?recommendation_id=r1",
            headers={"Authorization": "Bearer viewer-key"},
        )
        assert response.status_code == 403

    def test_403_operator_cannot_audit(self):
        response = client.get(
            "/api/uar/recommendations/audit?recommendation_id=r1",
            headers={"Authorization": "Bearer operator-key"},
        )
        assert response.status_code == 403

    def test_admin_can_audit(self):
        response = client.get(
            "/api/uar/recommendations/audit?recommendation_id=r1",
            headers={"Authorization": "Bearer admin-key"},
        )
        # 200 if data exists, 404 if recommendation not found
        assert response.status_code in (200, 404)


# ── export_trust_csv (GET /api/uar/recommendations/trust/export) ──


class TestExportTrustCsvAuth:
    def test_401_without_auth(self):
        response = client.get("/api/uar/recommendations/trust/export")
        assert response.status_code == 401
        assert response.json()["detail"]["error"] in (
            "unauthorized", "authentication_required"
        )

    def test_authenticated_can_export(self):
        response = client.get(
            "/api/uar/recommendations/trust/export",
            headers={"Authorization": "Bearer viewer-key"},
        )
        # CSV export may succeed or return empty depending on data
        assert response.status_code in (200, 404, 500)


# ── record_alert_action (POST /api/uar/alerts/{alert_id}/action) ──


class TestRecordAlertActionAuth:
    def test_401_without_auth(self):
        response = client.post(
            "/api/uar/alerts/alert-1/action",
            json={"status": "acted"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] in (
            "unauthorized", "authentication_required"
        )

    def test_400_invalid_status(self):
        response = client.post(
            "/api/uar/alerts/alert-1/action",
            json={"status": "invalid"},
            headers={"Authorization": "Bearer viewer-key"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_status"

    def test_404_alert_not_found(self):
        response = client.post(
            "/api/uar/alerts/nonexistent/action",
            json={"status": "acted"},
            headers={"Authorization": "Bearer viewer-key"},
        )
        assert response.status_code == 404
