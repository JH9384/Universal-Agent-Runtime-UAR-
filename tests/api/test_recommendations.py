"""Tests for the /api/uar/recommendations endpoint (Omega-5.1)."""

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
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


class TestRecommendationsEndpoint:
    def test_recommendations_requires_auth(self):
        response = client.get("/api/uar/recommendations")
        assert response.status_code == 401

    def test_recommendations_returns_structure(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations?hours=24&limit=100", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "generated_at" in data
        assert "hours" in data
        assert "runs_analyzed" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert "sources" in data

    def test_recommendations_fields(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations?hours=24&limit=100", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        for rec in data["recommendations"]:
            assert "category" in rec
            assert "priority" in rec
            assert "confidence" in rec
            assert "title" in rec
            assert "description" in rec
            assert "source" in rec
            assert "affected_runs" in rec

    def test_recommendations_cache_hit(self):
        """Second identical request should be cached (no error, fast path)."""
        headers = {"Authorization": "Bearer dev-key-12345"}
        url = "/api/uar/recommendations?hours=24&limit=100"
        r1 = client.get(url, headers=headers)
        r2 = client.get(url, headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == r2.json()


class TestRecommendationFeedback:
    def test_feedback_requires_auth(self):
        response = client.post("/api/uar/recommendations/feedback", json={})
        assert response.status_code == 401

    def test_feedback_valid_accept(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "action": "accept",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "recorded_at" in data

    def test_feedback_valid_reject(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "action": "reject",
            },
        )
        assert response.status_code == 200

    def test_feedback_valid_dismiss(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "action": "dismiss",
            },
        )
        assert response.status_code == 200

    def test_feedback_missing_fields(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={"recommendation_id": "abc123"},
        )
        assert response.status_code == 400

    def test_feedback_invalid_action(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "action": "maybe",
            },
        )
        assert response.status_code == 400
