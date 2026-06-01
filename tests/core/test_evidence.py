"""Tests for evidence module (Omega-6c)."""

from uar.core.evidence import aggregate_evidence, get_evidence


class TestGetEvidence:
    def test_missing_metadata_returns_none(self):
        assert get_evidence("r1", [], []) is None

    def test_basic_evidence(self):
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "remediate",
                "source": "pattern",
                "title": "Restart service",
                "confidence": 0.85,
                "run_id": "run-123",
            }
        ]
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": 1000,
            }
        ]
        evidence = get_evidence("r1", outcomes, metadata)
        assert evidence is not None
        assert evidence["recommendation_id"] == "r1"
        assert evidence["category"] == "remediate"
        assert evidence["confidence"] == 0.85
        assert evidence["run_id"] == "run-123"
        assert evidence["outcome"] == "resolved"

    def test_no_outcome(self):
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "remediate",
                "source": "pattern",
                "title": "Restart service",
            }
        ]
        evidence = get_evidence("r1", [], metadata)
        assert evidence is not None
        assert evidence["outcome"] is None

    def test_uses_latest_outcome(self):
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "remediate",
                "source": "pattern",
                "title": "Restart service",
            }
        ]
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "recurred",
                "recorded_at": 1000,
            },
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
                "recorded_at": 2000,
            },
        ]
        evidence = get_evidence("r1", outcomes, metadata)
        assert evidence["outcome"] == "resolved"


class TestAggregateEvidence:
    def test_empty_returns_empty(self):
        result = aggregate_evidence([], [])
        assert result["recommendation_types"] == []

    def test_basic_aggregation(self):
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
                "run_id": "run-a",
            },
            {
                "recommendation_id": "r2",
                "category": "restart_service",
                "run_id": "run-b",
            },
        ]
        outcomes = [
            {
                "recommendation_id": "r1",
                "outcome_type": "resolved",
            },
            {
                "recommendation_id": "r2",
                "outcome_type": "recurred",
            },
        ]
        result = aggregate_evidence(outcomes, metadata)
        types = result["recommendation_types"]
        assert len(types) == 1
        assert types[0]["type"] == "restart_service"
        assert types[0]["resolution_rate"] == 0.5
        assert types[0]["sample_size"] == 2
        assert types[0]["supporting_replays"] == 2

    def test_supporting_replays_counts_unique(self):
        """Same run_id for multiple outcomes counts once."""
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
                "run_id": "run-a",
            },
            {
                "recommendation_id": "r2",
                "category": "restart_service",
                "run_id": "run-a",
            },
        ]
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "resolved"},
            {"recommendation_id": "r2", "outcome_type": "resolved"},
        ]
        result = aggregate_evidence(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["supporting_replays"] == 1

    def test_no_run_id_means_zero_supporting_replays(self):
        metadata = [
            {
                "recommendation_id": "r1",
                "category": "restart_service",
            }
        ]
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "resolved"}
        ]
        result = aggregate_evidence(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["supporting_replays"] == 0

    def test_missing_metadata_skips(self):
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "resolved"}
        ]
        metadata = []
        result = aggregate_evidence(outcomes, metadata)
        assert result["recommendation_types"] == []

    def test_sorted_by_resolution_rate(self):
        metadata = [
            {"recommendation_id": "r1", "category": "cat_a"},
            {"recommendation_id": "r2", "category": "cat_b"},
        ]
        outcomes = [
            {"recommendation_id": "r1", "outcome_type": "resolved"},
            {"recommendation_id": "r2", "outcome_type": "recurred"},
        ]
        result = aggregate_evidence(outcomes, metadata)
        types = result["recommendation_types"]
        assert types[0]["type"] == "cat_a"
        assert types[1]["type"] == "cat_b"
