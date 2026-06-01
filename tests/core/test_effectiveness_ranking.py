"""Tests for effectiveness ranking module (Omega-6a)."""

import time

from uar.core.effectiveness_ranking import _decay_weight, compute_effectiveness


class TestDecayWeight:
    def test_today_is_full_weight(self):
        w = _decay_weight(time.time(), half_life_days=30.0)
        assert 0.99 < w <= 1.0

    def test_30_days_is_half(self):
        now = time.time()
        w = _decay_weight(now - 30 * 86400, half_life_days=30.0)
        assert 0.48 < w < 0.52

    def test_90_days_is_quarter(self):
        now = time.time()
        w = _decay_weight(now - 90 * 86400, half_life_days=30.0)
        assert 0.11 < w < 0.14

    def test_zero_half_life_returns_one(self):
        assert _decay_weight(time.time(), half_life_days=0.0) == 1.0


class TestComputeEffectiveness:
    def test_empty_returns_empty(self):
        result = compute_effectiveness([], [])
        assert result["recommendation_types"] == []

    def test_basic_resolution_rate(self):
        """3 resolved, 1 recurred = 0.75 resolution rate."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "recurred",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(outcomes, metadata, min_samples=1)
        types = result["recommendation_types"]
        assert len(types) == 1
        assert types[0]["type"] == "restart_service"
        assert types[0]["resolution_rate"] == 0.75
        assert types[0]["sample_size"] == 4

    def test_below_min_samples_filtered(self):
        """Only 2 outcomes, min_samples=5 → empty result."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(outcomes, metadata, min_samples=5)
        assert result["recommendation_types"] == []

    def test_bayesian_smoothing(self):
        """0 resolved, 1 recurred with alpha=1 beta=1 → (0+1)/(1+2)=0.33."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "recurred",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(
            outcomes, metadata, min_samples=1, alpha=1.0, beta=1.0
        )
        types = result["recommendation_types"]
        assert types[0]["smoothed_resolution_rate"] == round(1 / 3, 2)

    def test_drift_detection(self):
        """Historical: 10 resolved, 0 recurred (100%).
        Recent: 0 resolved, 5 recurred (0%).
        Drift should be -1.0."""
        now = time.time()
        outcomes = []
        # Historical (60 days ago)
        for _ in range(10):
            outcomes.append(
                {
                    "recommendation_id": "r1",
                    "outcome_type": "resolved",
                    "recorded_at": now - 60 * 86400,
                }
            )
        # Recent (5 days ago)
        for _ in range(5):
            outcomes.append(
                {
                    "recommendation_id": "r1",
                    "outcome_type": "recurred",
                    "recorded_at": now - 5 * 86400,
                }
            )
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(
            outcomes, metadata, min_samples=1, recent_window_days=30
        )
        types = result["recommendation_types"]
        assert types[0]["historical_resolution_rate"] == 1.0
        assert types[0]["recent_resolution_rate"] == 0.0
        assert types[0]["drift"] == -1.0

    def test_time_decay_affects_weighted_rate(self):
        """Old resolved outcomes weighted less than recent ones."""
        now = time.time()
        outcomes = [
            # Old: 2 resolved (weight ~0.25 each)
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now - 60 * 86400,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now - 60 * 86400,
            },
            # Recent: 1 recurred (full weight)
            {
                "recommendation_id": "r1",
                "outcome_type": "recurred",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(
            outcomes, metadata, min_samples=1, half_life_days=30
        )
        types = result["recommendation_types"]
        # Raw rate = 2/3 ≈ 0.67,
        # weighted should be lower due to decay
        weighted = types[0]["weighted_resolution_rate"]
        raw = types[0]["resolution_rate"]
        assert weighted < raw

    def test_unknown_outcomes_ignored(self):
        """Unknown outcomes should not count toward resolution rate."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "unknown",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "unknown",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            },
        ]
        result = compute_effectiveness(outcomes, metadata, min_samples=1)
        types = result["recommendation_types"]
        assert types[0]["sample_size"] == 1  # Only resolved counts
        assert types[0]["resolution_rate"] == 1.0

    def test_multiple_categories_sorted(self):
        """Categories sorted by weighted_resolution_rate descending."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
            {
                "recommendation_id": "r2",
                "outcome_type": "recurred",
                "recorded_at": now,
            },
        ]
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "cat_a",
            },
            {
                "recommendation_id": "r2",
                "category": "cat_b",
            },
        ]
        result = compute_effectiveness(outcomes, metadata, min_samples=1)
        types = result["recommendation_types"]
        assert len(types) == 2
        assert types[0]["type"] == "cat_a"
        assert types[1]["type"] == "cat_b"

    def test_missing_metadata_skips_outcome(self):
        """Outcomes without matching metadata are ignored."""
        now = time.time()
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": now,
            },
        ]
        metadata = []  # No metadata for r1
        result = compute_effectiveness(outcomes, metadata, min_samples=1)
        assert result["recommendation_types"] == []
