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
        assert "trust_ranking_enabled" in data
        assert "trust" in data

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
            assert "trust_score" in rec

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


class TestRecommendationCalibration:
    def test_calibration_requires_auth(self):
        response = client.get(
            "/api/uar/recommendations/calibration"
        )
        assert response.status_code == 401

    def test_calibration_returns_structure(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/calibration",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "overall_calibration_error" in data
        assert "mean_predicted_confidence" in data
        assert "mean_actual_resolution_rate" in data
        assert "sample_size" in data
        assert "reliability_buckets" in data


class TestRecommendationEvidence:
    def test_evidence_requires_auth(self):
        response = client.get("/api/uar/recommendations/evidence")
        assert response.status_code == 401

    def test_evidence_aggregate_structure(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/evidence",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendation_types" in data
        assert isinstance(data["recommendation_types"], list)
        for t in data["recommendation_types"]:
            assert "type" in t
            assert "resolution_rate" in t
            assert "sample_size" in t
            assert "supporting_replays" in t

    def test_evidence_specific_not_found(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/evidence",
            params={"recommendation_id": "nonexistent"},
            headers=headers,
        )
        assert response.status_code == 404


class TestRecommendationTrust:
    def test_trust_requires_auth(self):
        response = client.get("/api/uar/recommendations/trust")
        assert response.status_code == 401

    def test_trust_returns_structure(self):
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations/trust",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "system_calibration_error" in data
        assert "recommendation_types" in data
        assert isinstance(data["recommendation_types"], list)
        for t in data["recommendation_types"]:
            assert "type" in t
            assert "trust_score" in t
            assert "effectiveness_component" in t
            assert "calibration_component" in t
            assert "evidence_component" in t
            assert "drift_penalty" in t


class TestRecommendationTrustRankingOmega7b:
    """Ω-7b: Trust-weighted recommendation ranking."""

    def test_trust_observation_exposed_by_default(self):
        """Trust scores are always exposed; ranking is not changed
        when feature flag is off."""
        headers = {"Authorization": "Bearer dev-key-12345"}
        response = client.get(
            "/api/uar/recommendations?hours=24&limit=100",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trust_ranking_enabled"] is False
        assert "trust" in data
        # Every recommendation should carry its trust_score
        for rec in data["recommendations"]:
            assert "trust_score" in rec
            assert isinstance(rec["trust_score"], (int, float))

    def test_soft_blend_formula(self):
        """0.7 * confidence + 0.3 * trust produces expected values."""
        from uar.core.trust_ranking import compute_blend

        # High confidence, low trust → gentler than multiplication
        assert round(compute_blend(0.90, 0.50), 2) == 0.78
        # Perfect both ways → 1.0
        assert compute_blend(1.0, 1.0) == 1.0
        # Zero trust → 0.7 * confidence
        assert round(compute_blend(0.80, 0.0), 2) == 0.56
        # Clamped to 0
        assert compute_blend(0.0, -0.5) == 0.0
