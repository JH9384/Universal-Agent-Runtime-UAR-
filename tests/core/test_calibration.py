"""Tests for calibration module (Omega-6b)."""

from uar.core.calibration import compute_calibration


class TestComputeCalibration:
    def test_empty_returns_empty(self):
        result = compute_calibration([], [])
        assert result["sample_size"] == 0
        assert result["overall_calibration_error"] == 0.0
        assert result["reliability_buckets"] == []

    def test_well_calibrated(self):
        """5 predictions at 0.8, 4 resolved → actual 0.8.
        Calibration error ~ 0.0."""
        outcomes = []
        metadata = []
        for i in range(5):
            rid = f"r{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.8}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved" if i < 4 else "recurred",
                }
            )
        result = compute_calibration(outcomes, metadata)
        assert result["sample_size"] == 5
        assert result["mean_predicted_confidence"] == 0.8
        assert result["mean_actual_resolution_rate"] == 0.8
        assert abs(result["overall_calibration_error"]) <= 0.01

    def test_overconfident(self):
        """Predicted 0.95, Actual 0.4 → error +0.55."""
        outcomes = []
        metadata = []
        for i in range(10):
            rid = f"r{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.95}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved" if i < 4 else "recurred",
                }
            )
        result = compute_calibration(outcomes, metadata)
        assert result["mean_predicted_confidence"] == 0.95
        assert result["mean_actual_resolution_rate"] == 0.4
        assert result["overall_calibration_error"] == 0.55

    def test_underconfident(self):
        """Predicted 0.55, Actual 0.82 → error -0.27."""
        outcomes = []
        metadata = []
        for i in range(11):
            rid = f"r{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.55}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved" if i < 9 else "recurred",
                }
            )
        result = compute_calibration(outcomes, metadata)
        assert result["mean_predicted_confidence"] == 0.55
        assert result["mean_actual_resolution_rate"] == 0.82
        assert result["overall_calibration_error"] == -0.27

    def test_reliability_buckets(self):
        """Check that buckets are correctly formed."""
        outcomes = []
        metadata = []
        # Bucket 0.80-0.90: 2 predictions, 1 resolved
        for i in range(2):
            rid = f"h{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.85}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved" if i == 0 else "recurred",
                }
            )
        # Bucket 0.90-1.00: 2 predictions, 2 resolved
        for i in range(2):
            rid = f"l{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.95}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved",
                }
            )
        result = compute_calibration(outcomes, metadata)
        buckets = result["reliability_buckets"]
        assert len(buckets) == 2
        b80 = next(
            (b for b in buckets if b["bucket"] == "0.80-0.90"), None
        )
        assert b80 is not None
        assert b80["predicted_avg"] == 0.85
        assert b80["actual_rate"] == 0.5
        assert b80["calibration_error"] == 0.35

    def test_unknown_outcomes_ignored(self):
        """Unknown outcomes do not contribute to calibration."""
        metadata = [
            {"recommendation_id": "r1", "confidence": 0.9},
        ]
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "unknown"},
        ]
        result = compute_calibration(outcomes, metadata)
        assert result["sample_size"] == 0
        assert result["reliability_buckets"] == []

    def test_missing_metadata_skips(self):
        """Outcomes without matching metadata are ignored."""
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "resolved"},
        ]
        metadata = []
        result = compute_calibration(outcomes, metadata)
        assert result["sample_size"] == 0

    def test_min_bucket_samples_filters(self):
        """Buckets with fewer than min_bucket_samples excluded."""
        outcomes = []
        metadata = []
        for i in range(2):
            rid = f"r{i}"
            metadata.append(
                {"recommendation_id": rid, "confidence": 0.85}
            )
            outcomes.append(
                {
                    "recommendation_id": rid,
                    "outcome_type": "resolved",
                }
            )
        result = compute_calibration(
            outcomes, metadata, min_bucket_samples=5
        )
        assert result["reliability_buckets"] == []
