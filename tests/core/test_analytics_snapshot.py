"""Tests for uar.core.analytics_snapshot."""

from uar.core.analytics_snapshot import (
    AnalyticsSnapshot,
    SkillFailureCluster,
    TopologyNode,
    HotspotNode,
    RecipeStat,
    build_analytics_snapshot,
    extract_failure_clusters,
    extract_topology_hot_paths,
    extract_failure_hotspots,
    extract_recipe_intelligence,
    extract_confidence_drift,
)


def _make_run(
    run_id="r1",
    user_id="alice",
    status="success",
    skills=None,
    events=None,
    metadata=None,
    created_at=1000,
    duration_ms=100,
    confidence=None,
):
    return {
        "run_id": run_id,
        "user_id": user_id,
        "status": status,
        "skills": skills or [],
        "events": events or [],
        "metadata": metadata or {},
        "created_at": created_at,
        "duration_ms": duration_ms,
        "replay_confidence": confidence,
    }


class TestBuildAnalyticsSnapshot:
    def test_empty_runs(self):
        snap = build_analytics_snapshot([], "alice", False, 24, 1000)
        assert snap.runs_loaded == 0
        assert snap.runs_analyzed == 0
        assert snap.total_failures == 0

    def test_ownership_filter(self):
        runs = [
            _make_run("r1", user_id="alice"),
            _make_run("r2", user_id="bob"),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.runs_analyzed == 1

    def test_admin_sees_all(self):
        runs = [
            _make_run("r1", user_id="alice"),
            _make_run("r2", user_id="bob"),
        ]
        snap = build_analytics_snapshot(runs, "alice", True, 24, 1000)
        assert snap.runs_analyzed == 2

    def test_failure_clusters(self):
        runs = [
            _make_run(
                "r1",
                status="failure",
                events=[
                    {"skill": "s1", "error": "oops", "timestamp": 100},
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.total_failures == 1
        assert "s1" in snap.skill_clusters
        assert snap.skill_clusters["s1"].count == 1

    def test_topology_nodes_and_edges(self):
        runs = [
            _make_run("r1", skills=["a", "b", "c"]),
            _make_run("r2", skills=["a", "b"], status="failure"),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.topology_nodes["a"].invocations == 2
        assert snap.topology_nodes["a"].successes == 1
        assert snap.topology_nodes["a"].failures == 1
        assert "a\u2192b" in snap.topology_edges
        assert snap.topology_edges["a\u2192b"].transitions == 2
        assert snap.topology_edges["a\u2192b"].failures == 1

    def test_recipe_stats(self):
        runs = [
            _make_run(
                "r1",
                metadata={
                    "execution_order": [
                        {"type": "recipe", "content": "rec1"}
                    ]
                },
                confidence=0.95,
                duration_ms=120,
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert "rec1" in snap.recipe_stats
        rec = snap.recipe_stats["rec1"]
        assert rec.executions == 1
        assert rec.confidence_sum == 0.95
        assert rec.duration_sum == 120

    def test_hotspot_nodes(self):
        runs = [
            _make_run(
                "r1",
                skills=["a", "b"],
                events=[
                    {"skill": "a", "error": "boom", "timestamp": 100},
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.hotspot_nodes["a"].failures == 1
        assert snap.hotspot_nodes["b"].failures == 0
        assert "a\u2192b" in snap.hotspot_edges
        assert snap.hotspot_edges["a\u2192b"].failures == 1

    def test_skill_failure_counts(self):
        runs = [
            _make_run(
                "r1",
                events=[
                    {"skill": "s1", "error": "e1"},
                    {"skill": "s1", "error": "e2"},
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.skill_failure_counts["s1"] == 2
        assert len(snap.error_failure_counts) == 2


class TestExtractFailureClusters:
    def test_basic(self):
        snap = AnalyticsSnapshot()
        snap.skill_clusters["s1"] = SkillFailureCluster(
            skill="s1", count=5, runs={"r1", "r2"}
        )
        result = extract_failure_clusters(snap, top=10)
        assert result["total_failures"] == 0
        assert len(result["top_skills"]) == 1
        assert result["top_skills"][0]["run_count"] == 2


class TestExtractTopologyHotPaths:
    def test_basic(self):
        snap = AnalyticsSnapshot()
        snap.topology_nodes["a"] = TopologyNode(
            skill="a", invocations=3, successes=2, failures=1
        )
        result = extract_topology_hot_paths(snap, top=10)
        assert result["total_runs"] == 0
        assert result["nodes"][0]["success_rate"] == 0.67


class TestExtractFailureHotspots:
    def test_severity(self):
        snap = AnalyticsSnapshot()
        snap.hotspot_nodes["a"] = HotspotNode(
            skill="a", invocations=10, failures=6
        )
        result = extract_failure_hotspots(snap, top=10)
        node = result["nodes"][0]
        assert node["failure_rate"] == 0.6
        assert node["severity"] == "critical"


class TestExtractRecipeIntelligence:
    def test_classification(self):
        snap = AnalyticsSnapshot()
        snap.recipe_stats["r1"] = RecipeStat(
            recipe="r1", executions=5, successes=5,
            confidence_sum=4.5, confidence_count=5,
        )
        result = extract_recipe_intelligence(snap)
        rec = result["recipes"][0]
        assert rec["classification"] == "recommended"
        assert rec["avg_confidence"] == 0.9


class TestExtractConfidenceDrift:
    def test_empty(self):
        snap = AnalyticsSnapshot()
        result = extract_confidence_drift(snap, [], [], 24)
        assert result["state"] == "stable"
        assert result["current_score"] is None

    def test_with_history(self):
        import time
        snap = AnalyticsSnapshot()
        snap.skill_failure_counts["s1"] = 3
        now = time.time()
        mc = [
            {"timestamp": now - 3600, "replay_confidence": {"score": 80}},
            {"timestamp": now - 1800, "replay_confidence": {"score": 90}},
        ]
        result = extract_confidence_drift(snap, mc, [], 24)
        assert result["current_score"] == 90
        assert result["window_start_score"] == 80
        assert result["delta"] == 10
        assert result["state"] == "improving"
