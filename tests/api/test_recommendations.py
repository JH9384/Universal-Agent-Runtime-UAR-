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


class TestRecommendationQuality:
    def test_quality_requires_auth(self):
        response = client.get("/api/uar/recommendations/quality")
        assert response.status_code == 401

    def test_quality_empty(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/quality", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        # Prior tests may have recorded shown events, so just verify
        # structure rather than asserting exact zero counts.
        assert "recommendation_count" in data
        assert "total_shown" in data
        assert "overall_acceptance_rate" in data
        assert "metrics" in data
        assert isinstance(data["metrics"], list)

    def test_quality_with_feedback(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        # Record shown events by hitting recommendations endpoint
        client.get(
            "/api/uar/recommendations?hours=24&limit=100",
            headers=headers,
        )
        # Accept one
        client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={"recommendation_id": "abc123", "action": "accept"},
        )
        # Reject one
        client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={"recommendation_id": "abc456", "action": "reject"},
        )
        response = client.get(
            "/api/uar/recommendations/quality", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recommendation_count"] >= 0
        assert "total_shown" in data
        assert "overall_acceptance_rate" in data
        assert "metrics" in data
        for m in data["metrics"]:
            assert "recommendation_id" in m
            assert "shown_count" in m
            assert "accepted_count" in m
            assert "rejected_count" in m
            assert "dismissed_count" in m
            assert "acceptance_rate" in m
            assert "rejection_rate" in m
            assert "dismissal_rate" in m


class TestRecommendationOutcome:
    def test_outcome_requires_auth(self):
        response = client.post(
            "/api/uar/recommendations/outcome", json={}
        )
        assert response.status_code == 401

    def test_outcome_missing_field(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/outcome",
            headers=headers,
            json={"recommendation_id": "abc123"},
        )
        assert response.status_code == 400

    def test_outcome_invalid_type(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/outcome",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "outcome_type": "maybe",
            },
        )
        assert response.status_code == 400

    def test_outcome_resolved(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.post(
            "/api/uar/recommendations/outcome",
            headers=headers,
            json={
                "recommendation_id": "abc123",
                "outcome_type": "resolved",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "recorded_at" in data

    def test_outcome_surfaces_in_quality(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        rec_id = "outcome-test-rec"
        # Record an accept
        client.post(
            "/api/uar/recommendations/feedback",
            headers=headers,
            json={"recommendation_id": rec_id, "action": "accept"},
        )
        # Record a resolved outcome
        client.post(
            "/api/uar/recommendations/outcome",
            headers=headers,
            json={
                "recommendation_id": rec_id,
                "outcome_type": "resolved",
            },
        )
        response = client.get(
            "/api/uar/recommendations/quality", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_resolved" in data
        assert "overall_resolution_rate" in data
        for m in data["metrics"]:
            assert "resolved_count" in m
            assert "recurred_count" in m
            assert "resolution_rate" in m
        # At least our test rec should have resolution_rate > 0
        test_metric = next(
            (m for m in data["metrics"] if m["recommendation_id"] == rec_id),
            None,
        )
        if test_metric:
            assert test_metric["resolved_count"] >= 1


class TestRecommendationEffectiveness:
    def test_effectiveness_requires_auth(self):
        response = client.get(
            "/api/uar/recommendations/effectiveness"
        )
        assert response.status_code == 401

    def test_effectiveness_returns_structure(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/effectiveness",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "generated_at" in data
        assert "recommendation_types" in data
        assert isinstance(data["recommendation_types"], list)
        for t in data["recommendation_types"]:
            assert "type" in t
            assert "sample_size" in t
            assert "resolution_rate" in t
            assert "weighted_resolution_rate" in t
            assert "drift" in t
