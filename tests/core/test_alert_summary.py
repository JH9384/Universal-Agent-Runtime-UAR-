"""Tests for the alert summary endpoint logic."""

from uar.core.analytics_snapshot import build_analytics_snapshot


def _make_run(
    run_id="r1",
    user_id="alice",
    status="success",
    skills=None,
    events=None,
    metadata=None,
    created_at=1000000,
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
        "replay_confidence": confidence,
    }


class TestBuildAnalyticsSnapshotAlertInputs:
    def test_empty_runs_no_alerts(self):
        snap = build_analytics_snapshot([], "alice", False, 24, 1000)
        assert snap.runs_analyzed == 0
        assert snap.hotspot_total_failures == 0

    def test_critical_hotspot_detection(self):
        runs = [
            _make_run(
                "r1",
                status="failure",
                skills=["a", "b"],
                events=[
                    {"skill": "a", "error": "boom", "timestamp": 100},
                ],
            ),
            _make_run(
                "r2",
                status="failure",
                skills=["a", "b"],
                events=[
                    {"skill": "a", "error": "boom2", "timestamp": 100},
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.hotspot_nodes["a"].failures == 2
        assert snap.hotspot_nodes["a"].invocations == 2

    def test_confidence_drift_inputs(self):
        runs = [
            _make_run(
                "r1",
                events=[
                    {"skill": "s1", "error": "e1"},
                    {"skill": "s2", "error": "e2"},
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        assert snap.skill_failure_counts["s1"] == 1
        assert snap.skill_failure_counts["s2"] == 1
        assert "e1" in snap.error_failure_counts

    def test_recipe_intelligence_inputs(self):
        runs = [
            _make_run(
                "r1",
                metadata={
                    "execution_order": [
                        {"type": "recipe", "content": "rec1"}
                    ]
                },
                confidence=0.95,
            ),
            _make_run(
                "r2",
                status="failure",
                metadata={
                    "execution_order": [
                        {"type": "recipe", "content": "rec1"}
                    ]
                },
                confidence=0.85,
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)
        rec = snap.recipe_stats["rec1"]
        assert rec.executions == 2
        assert rec.successes == 1
        assert rec.failures == 1
