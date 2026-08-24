"""RE-AUDIT SPRINT Ω-5A — Recommendation Engine.

The system uses accumulated knowledge rather than merely storing it.

Not: Is this run correct?
Instead: What should the operator do next?
"""

from __future__ import annotations

from uar.core.multi_run_intelligence import (
    FailurePattern,
    RecoveryPath,
    TopologyEvolutionPoint,
)
from uar.core.operational_learning import (
    recommend_from_recurring_failures,
    recommend_from_recovery_atlas,
    recommend_from_topology_evolution,
    recommend_from_governance_trends,
    generate_all_recommendations,
)


# ------------------------------------------------------------------
# Ω-5A Tests
# ------------------------------------------------------------------


class TestOmega5ARecurringFailureRecommendations:
    """Recommendations from recurring failure patterns."""

    def test_single_recurring_pattern_generates_recommendation(self):
        """A recurring pattern should produce a remediate recommendation."""
        patterns = [
            FailurePattern(
                pattern_id="fp-001",
                signature="timeout::a+b",
                occurrences=8,
                affected_runs=["r1", "r2", "r3"],
            ),
        ]
        recs = recommend_from_recurring_failures(patterns)

        assert len(recs) == 1
        assert recs[0].category == "remediate"
        assert recs[0].source == "recurrence_engine"
        assert "timeout::a+b" in recs[0].title
        print(
            f"\n[Ω-5A] Recurring: {recs[0].title}, priority={recs[0].priority}"
        )

    def test_priority_scales_with_frequency(self):
        """More frequent patterns get higher priority."""
        patterns = [
            FailurePattern(
                pattern_id="fp-low",
                signature="err::a",
                occurrences=3,
                affected_runs=["r1"],
            ),
            FailurePattern(
                pattern_id="fp-med",
                signature="err::b",
                occurrences=6,
                affected_runs=["r1"],
            ),
            FailurePattern(
                pattern_id="fp-high",
                signature="err::c",
                occurrences=12,
                affected_runs=["r1"],
            ),
        ]
        recs = recommend_from_recurring_failures(patterns)

        assert recs[0].priority == "critical"
        assert recs[1].priority == "high"
        assert recs[2].priority == "medium"
        print(
            f"\n[Ω-5A] Priority scaling: "
            f"{recs[0].priority} / {recs[1].priority} / {recs[2].priority}"
        )

    def test_confidence_scales_with_frequency(self):
        """Confidence increases with more occurrences."""
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="err::a",
                occurrences=3,
                affected_runs=["r1"],
            ),
            FailurePattern(
                pattern_id="fp-2",
                signature="err::b",
                occurrences=10,
                affected_runs=["r1"],
            ),
        ]
        recs = recommend_from_recurring_failures(patterns)

        assert recs[0].confidence > recs[1].confidence
        print(
            f"\n[Ω-5A] Confidence: "
            f"high={recs[0].confidence:.2f}, "
            f"med={recs[1].confidence:.2f}"
        )

    def test_below_threshold_ignored(self):
        """Patterns below min_occurrences should be ignored."""
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="err::a",
                occurrences=1,
                affected_runs=["r1"],
            ),
        ]
        recs = recommend_from_recurring_failures(patterns, min_occurrences=3)
        assert len(recs) == 0


class TestOmega5ARecoveryAtlasRecommendations:
    """Recommendations from historical recovery patterns."""

    def test_high_success_recovery_recommended(self):
        """Recovery paths with high success rate generate recommendations."""
        paths = [
            RecoveryPath(
                failure_signature="timeout::a+b",
                operator_action="retry",
                outcome="completed",
                count=8,
                success_rate=0.85,
            ),
        ]
        recs = recommend_from_recovery_atlas(paths)

        assert len(recs) == 1
        assert recs[0].category == "remediate"
        assert recs[0].confidence == 0.85
        assert "retry" in recs[0].description
        print(
            f"\n[Ω-5A] Recovery: {recs[0].title}, "
            f"confidence={recs[0].confidence:.0%}"
        )

    def test_only_successful_paths_recommended(self):
        """Failed recovery paths should not be recommended."""
        paths = [
            RecoveryPath(
                failure_signature="timeout::a+b",
                operator_action="retry",
                outcome="failed",
                count=5,
                success_rate=0.0,
            ),
        ]
        recs = recommend_from_recovery_atlas(paths)
        assert len(recs) == 0

    def test_best_path_per_signature_selected(self):
        """When multiple paths for same signature, best one wins."""
        paths = [
            RecoveryPath(
                failure_signature="timeout::a+b",
                operator_action="retry",
                outcome="completed",
                count=3,
                success_rate=0.6,
            ),
            RecoveryPath(
                failure_signature="timeout::a+b",
                operator_action="reboot",
                outcome="completed",
                count=5,
                success_rate=0.9,
            ),
        ]
        recs = recommend_from_recovery_atlas(paths)

        assert len(recs) == 1
        assert "reboot" in recs[0].description
        assert recs[0].confidence == 0.9


class TestOmega5ATopologyRecommendations:
    """Recommendations from topology evolution."""

    def test_rapid_growth_detected(self):
        """Node growth >= 2x should trigger investigation."""
        points = [
            TopologyEvolutionPoint(
                timestamp=0.0,
                total_nodes=10,
                total_edges=20,
            ),
            TopologyEvolutionPoint(
                timestamp=1.0,
                total_nodes=25,
                total_edges=50,
            ),
        ]
        recs = recommend_from_topology_evolution(points)

        assert len(recs) >= 1
        assert any("growth" in r.title.lower() for r in recs)
        print(f"\n[Ω-5A] Topology: {recs[0].title}")

    def test_high_edge_ratio_detected(self):
        """Edge/node ratio > 20 should trigger optimization."""
        points = [
            TopologyEvolutionPoint(
                timestamp=0.0,
                total_nodes=10,
                total_edges=20,
            ),
            TopologyEvolutionPoint(
                timestamp=1.0,
                total_nodes=10,
                total_edges=250,
            ),
        ]
        recs = recommend_from_topology_evolution(points)

        assert any("edge-to-node" in r.title.lower() for r in recs)

    def test_persistent_hot_region_detected(self):
        """Same hot region for 3+ periods should trigger optimization."""
        points = [
            TopologyEvolutionPoint(
                timestamp=0.0,
                total_nodes=10,
                total_edges=20,
                hot_region="skill_x",
            ),
            TopologyEvolutionPoint(
                timestamp=1.0,
                total_nodes=10,
                total_edges=20,
                hot_region="skill_x",
            ),
            TopologyEvolutionPoint(
                timestamp=2.0,
                total_nodes=10,
                total_edges=20,
                hot_region="skill_x",
            ),
        ]
        recs = recommend_from_topology_evolution(points)

        assert any("hot region" in r.title.lower() for r in recs)
        assert any("skill_x" in r.title for r in recs)
        print(f"\n[Ω-5A] Hot region: {recs[0].title}")

    def test_empty_points_returns_empty(self):
        """No topology data should produce no recommendations."""
        assert recommend_from_topology_evolution([]) == []


class TestOmega5AGovernanceTrendRecommendations:
    """Recommendations from governance trend analysis."""

    def test_approval_rate_drop_detected(self):
        """Approval rate dropping 20%+ should trigger review."""
        summaries = [
            {"approval_rate": 1.0, "total_records": 100},
            {"approval_rate": 0.7, "total_records": 100},
        ]
        recs = recommend_from_governance_trends(summaries)

        assert len(recs) >= 1
        assert any("Approval rate declining" in r.title for r in recs)
        print(
            f"\n[Ω-5A] Governance: {recs[0].title}, "
            f"priority={recs[0].priority}"
        )

    def test_tampered_rate_elevated_detected(self):
        """Tampered rate > 10% and rising should trigger critical alert."""
        summaries = [
            {"tampered": 5, "total_records": 100, "approval_rate": 1.0},
            {"tampered": 15, "total_records": 100, "approval_rate": 1.0},
        ]
        recs = recommend_from_governance_trends(summaries)

        assert any("Tampered" in r.title for r in recs)
        tampered_rec = next(r for r in recs if "Tampered" in r.title)
        assert tampered_rec.priority == "critical"

    def test_certification_rate_drop_detected(self):
        """Certification rate dropping below 95% should trigger alert."""
        summaries = [
            {
                "certification_rate": 0.98,
                "approval_rate": 1.0,
                "total_records": 100,
            },
            {
                "certification_rate": 0.92,
                "approval_rate": 1.0,
                "total_records": 100,
            },
        ]
        recs = recommend_from_governance_trends(summaries)

        assert any("Certification rate declining" in r.title for r in recs)

    def test_insufficient_history_returns_empty(self):
        """Single summary should produce no trend recommendations."""
        summaries = [
            {"approval_rate": 1.0, "total_records": 100},
        ]
        assert recommend_from_governance_trends(summaries) == []


class TestOmega5AUnifiedRecommendations:
    """Test the unified recommendation generator."""

    def test_unified_prioritizes_critical(self):
        """Critical recommendations should appear first."""
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="err::a",
                occurrences=12,
                affected_runs=["r1"],
            ),
            FailurePattern(
                pattern_id="fp-2",
                signature="err::b",
                occurrences=3,
                affected_runs=["r1"],
            ),
        ]
        recs = generate_all_recommendations(recurring_patterns=patterns)

        assert recs[0].priority == "critical"
        assert "err::a" in recs[0].title

    def test_unified_combines_all_sources(self):
        """Multiple sources should all contribute to output."""
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="err::a",
                occurrences=5,
                affected_runs=["r1"],
            ),
        ]
        paths = [
            RecoveryPath(
                failure_signature="err::a",
                operator_action="retry",
                outcome="completed",
                count=5,
                success_rate=0.8,
            ),
        ]
        points = [
            TopologyEvolutionPoint(
                timestamp=0.0,
                total_nodes=10,
                total_edges=20,
            ),
            TopologyEvolutionPoint(
                timestamp=1.0,
                total_nodes=10,
                total_edges=250,
            ),
        ]
        summaries = [
            {"approval_rate": 1.0, "total_records": 100},
            {"approval_rate": 0.7, "total_records": 100},
        ]

        recs = generate_all_recommendations(
            recurring_patterns=patterns,
            recovery_paths=paths,
            topology_points=points,
            governance_summaries=summaries,
        )

        sources = {r.source for r in recs}
        assert "recurrence_engine" in sources
        assert "recovery_atlas" in sources
        assert "topology_evolution" in sources
        assert "governance_insights" in sources
        print(
            f"\n[Ω-5A] Unified: {len(recs)} recs from {len(sources)} sources"
        )

    def test_recommendation_structure(self):
        """All recommendations should have required fields."""
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="err::a",
                occurrences=5,
                affected_runs=["r1"],
            ),
        ]
        recs = generate_all_recommendations(recurring_patterns=patterns)

        for rec in recs:
            d = rec.to_dict()
            assert d["category"]
            assert d["priority"]
            assert 0.0 <= d["confidence"] <= 1.0
            assert d["title"]
            assert d["description"]
            assert d["source"]

    def test_operational_learning_value_proposition(self):
        """
        Ω-5A value: system suggests action from history.

        Before Ω-5A: Operator sees 'timeout::a+b occurred 8 times'
        After Ω-5A:  Operator sees recommendation with action.
        """
        patterns = [
            FailurePattern(
                pattern_id="fp-1",
                signature="timeout::a+b",
                occurrences=8,
                affected_runs=[f"r{i}" for i in range(8)],
            ),
        ]
        recs = generate_all_recommendations(recurring_patterns=patterns)

        assert len(recs) > 0
        rec = recs[0]
        assert "timeout::a+b" in rec.title
        assert (
            "root cause" in rec.description.lower()
            or "remediate" in rec.description.lower()
        )
        assert rec.confidence > 0.5
        print(
            f"\n[Ω-5A] Value proposition: "
            f"'{rec.title}' ({rec.priority}, "
            f"confidence={rec.confidence:.0%})"
        )
