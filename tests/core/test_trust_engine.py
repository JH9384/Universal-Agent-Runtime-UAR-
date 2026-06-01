"""Tests for trust engine module (Omega-7a)."""

from uar.core.trust_engine import compute_trust


class TestComputeTrust:
    def test_empty_returns_empty(self):
        result = compute_trust([], [])
        assert result["recommendation_types"] == []
        assert result["system_calibration_error"] == 0.0

    def test_perfect_trust(self):
        """All components perfect → trust near 1.0."""
        import time
        now = time.time()
        metadata = [
            {
                "recommendation_id": f"r{i}",
                "category": "restart_service",
                "confidence": 0.9,
                "run_id": f"run-{i}",
            }
            for i in range(5)
        ]
        outcomes = [
            {
                "recommendation_id": f"r{i}",
                "outcome_type": "resolved",
                "recorded_at": now,
            }
            for i in range(5)
        ]
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert len(types) == 1
        assert types[0]["type"] == "restart_service"
        assert types[0]["effectiveness_component"] == 1.0
        assert types[0]["calibration_component"] >= 0.9
        assert 0.6 < types[0]["trust_score"] < 0.8

    def test_overconfidence_reduces_trust(self):
        """System overconfidence lowers calibration_component."""
        metadata = [
            {
                "recommendation_id": f"r{i}",
                "category": "restart_service",
                "confidence": 0.95,
                "run_id": f"run-{i}",
            }
            for i in range(5)
        ]
        outcomes = [
            {"recommendation_id": f"r{i}", "outcome_type": "recurred"}
            for i in range(5)
        ]
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["calibration_component"] < 1.0
        assert types[0]["trust_score"] < 0.7

    def test_drift_penalty(self):
        """Negative drift reduces trust score."""
        import time
        now = time.time()
        metadata = [
            {
                "recommendation_id": f"r{i}",
                "category": "restart_service",
                "confidence": 0.8,
                "run_id": f"run-{i}",
            }
            for i in range(5)
        ]
        outcomes = (
            [
                {
                    "recommendation_id": f"r{i}",
                    "outcome_type": "resolved",
                    "recorded_at": now - 60 * 86400,
                }
                for i in range(5)
            ]
            + [
                {
                    "recommendation_id": f"r{i}",
                    "outcome_type": "recurred",
                    "recorded_at": now - 5 * 86400,
                }
                for i in range(5)
            ]
        )
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["drift_penalty"] > 0.0
        assert types[0]["trust_score"] < types[0]["effectiveness_component"]

    def test_evidence_component_with_many_samples(self):
        """Many samples and replays boost evidence_component."""
        metadata = []
        outcomes = []
        for i in range(100):
            rid = f"r{i}"
            metadata.append(
                {
                    "recommendation_id": rid,
                    "category": "restart_service",
                    "confidence": 0.8,
                    "run_id": f"run-{i}",
                }
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved",
                }
            )
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["evidence_component"] == 1.0

    def test_trust_clamped_to_zero(self):
        """Severe drift can drive trust to 0.0."""
        import time
        now = time.time()
        metadata = [
            {
                "recommendation_id": f"r{i}",
                "category": "restart_service",
                "confidence": 0.99,
                "run_id": f"run-{i}",
            }
            for i in range(5)
        ]
        outcomes = [
            {
                "recommendation_id": f"r{i}",
                "outcome_type": "recurred",
                "recorded_at": now,
            }
            for i in range(5)
        ]
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["trust_score"] < 0.1

    def test_sorted_by_trust_descending(self):
        """Types sorted by trust_score descending."""
        metadata = (
            [
                {
                    "recommendation_id": f"r{i}",
                    "category": "cat_a",
                    "confidence": 0.9,
                }
                for i in range(5)
            ]
            + [
                {
                    "recommendation_id": f"r{i+5}",
                    "category": "cat_b",
                    "confidence": 0.5,
                }
                for i in range(5)
            ]
        )
        outcomes = (
            [
                {"recommendation_id": f"r{i}", "outcome_type": "resolved"}
                for i in range(5)
            ]
            + [
                {"recommendation_id": f"r{i+5}", "outcome_type": "recurred"}
                for i in range(5)
            ]
        )
        result = compute_trust(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["type"] == "cat_a"
        assert types[1]["type"] == "cat_b"
        assert types[0]["trust_score"] > types[1]["trust_score"]
