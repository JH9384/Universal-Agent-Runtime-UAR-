"""RE-AUDIT SPRINT Ω-1 — Track 2: Analytics Accuracy.

Verify that all analytics panels derive from the same AnalyticsSnapshot
truth and do not perform independent counting.

Key invariants:
- total_failures == sum(skill_failure_counts) == sum(error_failure_counts)
- hotspot_total_failures <= total_failures (counts skills, not events)
- All panels use build_analytics_snapshot + extractors (no panel-local agg)
"""

from uar.core.analytics_snapshot import (
    build_analytics_snapshot,
    extract_failure_clusters,
    extract_failure_hotspots,
    extract_confidence_drift,
    extract_recipe_intelligence,
    extract_topology_hot_paths,
)


def _make_run(
    run_id="r1",
    status="success",
    skills=None,
    events=None,
    metadata=None,
    created_at=1000,
    user_id="alice",
):
    return {
        "run_id": run_id,
        "id": run_id,
        "status": status,
        "skills": skills or [],
        "events": events or [],
        "metadata": metadata or {},
        "created_at": created_at,
        "timestamp": created_at,
        "user_id": user_id,
        "user": user_id,
    }


def _make_error_event(skill="skill_a", error="timeout", timestamp=1000):
    return {
        "skill": skill,
        "error": error,
        "type": "error",
        "timestamp": timestamp,
    }


class TestAASingleFailedRun:
    """AA-1: Single failed run — all panels agree on basics."""

    def test_all_panels_use_same_snapshot(self):
        run = _make_run(
            run_id="r1",
            status="failed",
            skills=["skill_a", "skill_b"],
            events=[
                _make_error_event("skill_a", "timeout"),
            ],
        )
        snap = build_analytics_snapshot([run], "alice", False, 24, 1000)

        # All extractors run from the same snap
        fc = extract_failure_clusters(snap, top=10)
        hs = extract_failure_hotspots(snap, top=10)
        cd = extract_confidence_drift(snap, [], [], 24)
        tp = extract_topology_hot_paths(snap, top=10)

        # Total runs analyzed must match across panels that report it
        assert fc["total_runs_scanned"] == 1
        assert hs["total_runs"] == 1
        assert tp["total_runs"] == 1
        assert cd["failure_summary"]["total_failures"] == 1

    def test_failure_counts_consistent_within_snapshot(self):
        run = _make_run(
            run_id="r1",
            status="failed",
            skills=["skill_a", "skill_b"],
            events=[
                _make_error_event("skill_a", "timeout"),
                _make_error_event("skill_a", "timeout"),
            ],
        )
        snap = build_analytics_snapshot([run], "alice", False, 24, 1000)

        # total_failures counts events
        assert snap.total_failures == 2
        # skill_failure_counts also counts events
        assert sum(snap.skill_failure_counts.values()) == 2
        # hotspot_total_failures counts distinct failed skills per run
        assert snap.hotspot_total_failures == 1

    def test_extractors_reflect_snapshot_truth(self):
        run = _make_run(
            run_id="r1",
            status="failed",
            skills=["skill_a", "skill_b"],
            events=[_make_error_event("skill_a", "timeout")],
        )
        snap = build_analytics_snapshot([run], "alice", False, 24, 1000)

        fc = extract_failure_clusters(snap, top=10)
        hs = extract_failure_hotspots(snap, top=10)
        cd = extract_confidence_drift(snap, [], [], 24)

        # Failure clusters: total_failures = event count
        assert fc["total_failures"] == 1
        # Hotspots: total_failures = distinct failed skills
        assert hs["total_failures"] == 1
        # Drift: failure_summary uses skill_failure_counts
        assert cd["failure_summary"]["total_failures"] == 1


class TestAAMultipleFailures:
    """AA-2: Multiple failures across runs — aggregation agrees."""

    def test_two_runs_same_skill_multiple_errors(self):
        runs = [
            _make_run(
                run_id="r1",
                status="failed",
                skills=["skill_a"],
                events=[
                    _make_error_event("skill_a", "timeout"),
                    _make_error_event("skill_a", "timeout"),
                ],
            ),
            _make_run(
                run_id="r2",
                status="failed",
                skills=["skill_a"],
                events=[_make_error_event("skill_a", "crash")],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        # Event-level counts
        assert snap.total_failures == 3
        assert sum(snap.skill_failure_counts.values()) == 3

        # Hotspot counts distinct failed skills per run
        assert snap.hotspot_total_failures == 2

        fc = extract_failure_clusters(snap, top=10)
        assert fc["total_failures"] == 3
        assert fc["top_skills"][0]["count"] == 3

        hs = extract_failure_hotspots(snap, top=10)
        assert hs["total_failures"] == 2
        assert hs["nodes"][0]["failures"] == 2


class TestAAMixedPassFail:
    """AA-3: Mixed pass/fail population — ratios and counts agree."""

    def test_three_runs_one_pass_two_fail(self):
        runs = [
            _make_run(run_id="r1", status="success", skills=["s1"]),
            _make_run(
                run_id="r2",
                status="failed",
                skills=["s1"],
                events=[_make_error_event("s1", "err")],
            ),
            _make_run(
                run_id="r3",
                status="failed",
                skills=["s1"],
                events=[_make_error_event("s1", "err")],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        assert snap.runs_analyzed == 3
        assert snap.total_failures == 2

        fc = extract_failure_clusters(snap, top=10)
        assert fc["total_runs_scanned"] == 3
        assert fc["total_failures"] == 2

        hs = extract_failure_hotspots(snap, top=10)
        assert hs["total_runs"] == 3
        # 2 runs with failed skill s1
        assert hs["total_failures"] == 2

        tp = extract_topology_hot_paths(snap, top=10)
        assert tp["total_runs"] == 3
        # Node invocations across all runs
        assert tp["nodes"][0]["invocations"] == 3
        # success_rate reflects 1 failure out of 3 = 0.67
        assert tp["nodes"][0]["success_rate"] == round(1 / 3, 2)

    def test_success_rate_math(self):
        runs = [
            _make_run(run_id="r1", status="success", skills=["s1"]),
            _make_run(run_id="r2", status="success", skills=["s1"]),
            _make_run(
                run_id="r3",
                status="failed",
                skills=["s1"],
                events=[_make_error_event("s1", "err")],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        tp = extract_topology_hot_paths(snap, top=10)
        node = tp["nodes"][0]
        # success_rate = successes / invocations
        assert node["success_rate"] == round(2 / 3, 2)
        # Topology nodes don't expose failure_rate directly
        assert round(1 - node["success_rate"], 2) == round(1 / 3, 2)


class TestAADriftHotspotOverlap:
    """AA-4: Drift and hotspot overlap — no double counting in snapshot."""

    def test_same_failure_appears_in_drift_and_hotspot(self):
        run = _make_run(
            run_id="r1",
            status="failed",
            skills=["s1", "s2"],
            events=[_make_error_event("s1", "err")],
        )
        snap = build_analytics_snapshot([run], "alice", False, 24, 1000)

        # Drift contributors and hotspots share the same underlying count
        cd = extract_confidence_drift(snap, [], [], 24)
        hs = extract_failure_hotspots(snap, top=10)

        drift_skills = {
            c["skill"] for c in cd["failure_summary"]["top_skills"]
        }
        hotspot_skills = {n["skill"] for n in hs["nodes"]}

        # Both should see s1 as failing
        assert "s1" in drift_skills
        assert "s1" in hotspot_skills

        # Counts should reflect the same single error event
        s1_drift = next(
            c for c in cd["failure_summary"]["top_skills"]
            if c["skill"] == "s1"
        )
        assert s1_drift["count"] == 1


class TestAASnapshotConsistency:
    """AA-10: Snapshot is the single source of truth."""

    def test_no_panel_local_aggregation_in_extractors(self):
        """Extractors must not rescan runs or perform independent counts."""
        runs = [
            _make_run(
                run_id="r1",
                status="failed",
                skills=["s1"],
                events=[_make_error_event("s1", "err")],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        # All extractors must return without raising
        fc = extract_failure_clusters(snap, top=10)
        hs = extract_failure_hotspots(snap, top=10)
        cd = extract_confidence_drift(snap, [], [], 24)
        ri = extract_recipe_intelligence(snap)
        assert ri is not None
        tp = extract_topology_hot_paths(snap, top=10)

        # Each must derive counts from snap fields, not recompute
        assert fc["total_failures"] == snap.total_failures
        assert hs["total_failures"] == snap.hotspot_total_failures
        assert (
            cd["failure_summary"]["total_failures"]
            == sum(snap.skill_failure_counts.values())
        )
        assert tp["total_runs"] == snap.runs_analyzed

    def test_empty_store_all_zero(self):
        """AA-8: Empty store — all panels return zero/empty."""
        snap = build_analytics_snapshot([], "alice", False, 24, 1000)

        assert snap.runs_analyzed == 0
        assert snap.total_failures == 0
        assert snap.hotspot_total_failures == 0

        fc = extract_failure_clusters(snap, top=10)
        assert fc["total_failures"] == 0
        assert fc["top_skills"] == []

        hs = extract_failure_hotspots(snap, top=10)
        assert hs["total_failures"] == 0
        assert hs["nodes"] == []

        cd = extract_confidence_drift(snap, [], [], 24)
        assert cd["failure_summary"]["total_failures"] == 0

        ri = extract_recipe_intelligence(snap)
        assert ri["recipes"] == []

        tp = extract_topology_hot_paths(snap, top=10)
        assert tp["total_runs"] == 0


class TestAALargePopulation:
    """AA-7: Large population — performance and correctness."""

    def test_1000_runs_consistency(self):
        runs = []
        for i in range(1000):
            if i % 4 == 0:
                # Failed run with one error event
                runs.append(_make_run(
                    run_id=f"r{i}",
                    status="failed",
                    skills=["s1"],
                    events=[_make_error_event("s1", "err")],
                    created_at=1000 + i,
                ))
            else:
                runs.append(_make_run(
                    run_id=f"r{i}",
                    status="success",
                    skills=["s1"],
                    created_at=1000 + i,
                ))

        snap = build_analytics_snapshot(runs, "alice", False, 24, 50000)

        # 250 failed runs, each with 1 error event
        assert snap.total_failures == 250
        assert snap.runs_analyzed == 1000

        fc = extract_failure_clusters(snap, top=10)
        assert fc["total_failures"] == 250
        assert fc["total_runs_scanned"] == 1000

        hs = extract_failure_hotspots(snap, top=10)
        assert hs["total_failures"] == 250  # 250 distinct failed skills
        assert hs["total_runs"] == 1000

        tp = extract_topology_hot_paths(snap, top=10)
        assert tp["total_runs"] == 1000
        assert tp["nodes"][0]["invocations"] == 1000
        # 750 successes / 1000 = 0.75
        assert tp["nodes"][0]["success_rate"] == 0.75


class TestAAKnownDiscrepancy:
    """Document the known relationship between event-count and skill-count.

    This is not a bug — it is a semantic difference:
    - total_failures counts error events (can be >1 per skill per run)
    - hotspot_total_failures counts distinct failed skills per run

    Both are correct for their respective use cases.
    The audit verifies they maintain their invariant relationship.
    """

    def test_event_count_ge_skill_count(self):
        """Total failures >= hotspot failures always."""
        runs = [
            _make_run(
                run_id="r1",
                status="failed",
                skills=["s1", "s2"],
                events=[
                    _make_error_event("s1", "err"),
                    _make_error_event("s1", "err"),
                    _make_error_event("s2", "err"),
                ],
            ),
            _make_run(
                run_id="r2",
                status="failed",
                skills=["s1"],
                events=[_make_error_event("s1", "err")],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        # 4 error events total
        assert snap.total_failures == 4
        # 2 runs, each with at least one failed skill
        # r1: s1,s2 (2 skills); r2: s1 (1 skill) -> 3 total
        assert snap.hotspot_total_failures == 3

        # Invariant: event count >= skill count
        assert snap.total_failures >= snap.hotspot_total_failures

    def test_single_error_per_skill_equality(self):
        """When each failed skill has exactly one error, counts match."""
        runs = [
            _make_run(
                run_id="r1",
                status="failed",
                skills=["s1", "s2"],
                events=[
                    _make_error_event("s1", "err"),
                    _make_error_event("s2", "err"),
                ],
            ),
        ]
        snap = build_analytics_snapshot(runs, "alice", False, 24, 1000)

        assert snap.total_failures == 2
        assert snap.hotspot_total_failures == 2
        assert snap.total_failures == snap.hotspot_total_failures
