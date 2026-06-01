"""RE-AUDIT SPRINT Ω-4B — Multi-Run Intelligence.

Learn what collections of trustworthy runs can teach
the system about itself.

Not: Is this run correct?
Instead: What do many runs reveal collectively?
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

import dataclasses

from uar.core.analytics_snapshot import build_analytics_snapshot
from uar.core.executor import make_executor_event
from uar.core.multi_run_intelligence import (
    find_recurring_failures,
    build_recovery_atlas,
    track_topology_evolution,
    rank_certification_failures,
    summarize_operational_memory,
)
from uar.core.replay import run_record_from_events, certify_replay


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_run(
    run_id: str,
    skills: List[str],
    status: str = "completed",
    error: str = "",
    timestamp: float = 0.0,
) -> Dict[str, Any]:
    """Build a run dict with specified outcome."""
    events = [
        make_executor_event(
            "start", run_id, "g1",
            payload={"skills": skills},
        ),
    ]
    for skill in skills:
        if status == "completed":
            events.append(
                make_executor_event(
                    "skill_complete", run_id, "g1", skill=skill,
                )
            )
        else:
            events.append(
                make_executor_event(
                    "skill_failed", run_id, "g1",
                    skill=skill, error=error or "failure",
                )
            )
            break

    events.append(
        make_executor_event(
            "complete", run_id, "g1",
            payload={
                "status": status,
                "outputs": [] if status != "completed" else [{"ok": True}],
                "errors": [error] if error else [],
                "final_context": {},
            },
        )
    )
    record = run_record_from_events(events)
    d = dataclasses.asdict(record)
    d["timestamp"] = timestamp
    return d


# ------------------------------------------------------------------
# Ω-4B Tests
# ------------------------------------------------------------------

class TestOmega4BRecurrenceEngine:
    """Find recurring failure patterns across runs."""

    def test_find_recurring_failures_detects_patterns(self):
        """Repeated identical failures should be grouped."""
        runs = [
            _make_run(f"r{i}", ["a", "b"], "failed", "timeout")
            for i in range(5)
        ]
        patterns = find_recurring_failures(runs, min_occurrences=2)

        assert len(patterns) == 1
        assert patterns[0].occurrences == 5
        assert "timeout" in patterns[0].signature
        print(
            f"\n[Ω-4B] Recurring pattern: {patterns[0].signature}, "
            f"occurrences={patterns[0].occurrences}"
        )

    def test_find_recurring_failures_ignores_unique(self):
        """Single-occurrence failures should not be reported."""
        runs = [
            _make_run("r1", ["a"], "failed", "timeout"),
            _make_run("r2", ["a"], "failed", "network"),
        ]
        patterns = find_recurring_failures(runs, min_occurrences=2)

        assert len(patterns) == 0

    def test_find_recurring_failures_mixed_success(self):
        """Successful runs should not appear in failure patterns."""
        runs = [
            _make_run("r1", ["a"], "completed"),
            _make_run("r2", ["a"], "failed", "timeout"),
            _make_run("r3", ["a"], "failed", "timeout"),
        ]
        patterns = find_recurring_failures(runs, min_occurrences=2)

        assert len(patterns) == 1
        assert patterns[0].occurrences == 2


class TestOmega4BRecoveryAtlas:
    """Map failure signatures to recovery outcomes."""

    def test_build_recovery_atlas_ranks_by_frequency(self):
        """Most common failure-outcome pairs should be first."""
        runs = [
            _make_run("r1", ["a"], "failed", "timeout"),
            _make_run("r2", ["a"], "failed", "timeout"),
            _make_run("r3", ["a"], "completed"),
        ]
        atlas = build_recovery_atlas(runs)

        assert len(atlas) > 0
        # timeout::a should be most common
        assert atlas[0].failure_signature.startswith("timeout")
        assert atlas[0].count >= 2
        print(
            f"\n[Ω-4B] Recovery atlas top: "
            f"{atlas[0].failure_signature} -> {atlas[0].outcome} "
            f"({atlas[0].count}x)"
        )

    def test_build_recovery_atlas_includes_all_outcomes(self):
        """Both completed and failed outcomes should appear."""
        runs = [
            _make_run("r1", ["a"], "failed", "timeout"),
            _make_run("r2", ["a"], "completed"),
        ]
        atlas = build_recovery_atlas(runs)

        outcomes = {p.outcome for p in atlas}
        assert "completed" in outcomes
        assert "failed" in outcomes


class TestOmega4BTopologyEvolution:
    """Track topology changes over time."""

    def test_track_topology_growth(self):
        """Topology should show growth over accumulating snapshots."""
        snapshots = []
        all_runs: List[Dict[str, Any]] = []

        # Build 3 snapshots with increasing data
        for batch in range(3):
            for i in range(5):
                all_runs.append(
                    _make_run(f"te-{batch}-{i}", ["skill" + str(batch)])
                )
            snap = build_analytics_snapshot(
                all_runs, "alice", False, 24, 50000,
            )
            snapshots.append(snap)

        points = track_topology_evolution(snapshots)

        assert len(points) == 3
        assert points[0].total_nodes <= points[1].total_nodes
        assert points[1].total_nodes <= points[2].total_nodes
        print(
            f"\n[Ω-4B] Topology evolution: "
            f"{points[0].total_nodes} -> "
            f"{points[1].total_nodes} -> "
            f"{points[2].total_nodes} nodes"
        )

    def test_track_topology_hot_region(self):
        """Hot region should identify the most active node."""
        all_runs = [
            _make_run(f"hr-{i}", ["hot_skill"])
            for i in range(10)
        ]
        snap = build_analytics_snapshot(
            all_runs, "alice", False, 24, 50000,
        )
        points = track_topology_evolution([snap])

        assert points[0].hot_region is not None
        print(f"\n[Ω-4B] Hot region: {points[0].hot_region}")


class TestOmega4BCertificationFailureRanking:
    """Identify which certification failures occur most."""

    def test_rank_certification_failures_by_frequency(self):
        """Most common failure types should be ranked first."""
        certs = [
            {"fidelity_score": 100.0},
            {
                "fidelity_score": 0.0,
                "reconstruction_error": "missing terminal",
            },
            {
                "fidelity_score": 0.0,
                "reconstruction_error": "missing terminal",
            },
            {
                "fidelity_score": 0.0,
                "reconstruction_error": "invalid payload",
            },
        ]
        ranked = rank_certification_failures(certs)

        assert len(ranked) == 2
        assert ranked[0]["error_type"] == "missing terminal"
        assert ranked[0]["count"] == 2
        assert ranked[1]["error_type"] == "invalid payload"
        assert ranked[1]["count"] == 1
        print(
            f"\n[Ω-4B] Top cert failure: "
            f"{ranked[0]['error_type']} "
            f"({ranked[0]['count']}x, "
            f"{ranked[0]['percentage']:.1f}%)"
        )

    def test_rank_certification_no_failures(self):
        """All-pass certifications should produce empty ranking."""
        certs = [
            {"fidelity_score": 100.0},
            {"fidelity_score": 100.0},
        ]
        ranked = rank_certification_failures(certs)

        assert len(ranked) == 0


class TestOmega4BOperationalMemory:
    """Aggregate multi-run intelligence into operational memory."""

    def test_summarize_operational_memory_structure(self):
        """Summary should contain all expected keys."""
        runs = [
            _make_run("r1", ["a"], "completed"),
            _make_run("r2", ["a"], "failed", "timeout"),
            _make_run("r3", ["a"], "failed", "timeout"),
        ]
        certs = [
            certify_replay(run_record_from_events(r["events"]))
            for r in runs
        ]
        summary = summarize_operational_memory(runs, certs)

        assert summary["total_runs"] == 3
        assert summary["failure_rate"] > 0
        assert len(summary["recurring_patterns"]) > 0
        assert len(summary["recovery_paths"]) > 0
        assert summary["certification_health"] is not None
        rate = summary["certification_health"]["certification_rate"]
        assert rate == 1.0
        print(
            f"\n[Ω-4B] Operational memory: "
            f"{summary['total_runs']} runs, "
            f"failure_rate={summary['failure_rate']:.2f}, "
            f"patterns={len(summary['recurring_patterns'])}, "
            f"cert_rate={rate:.0%}"
        )

    def test_summarize_without_certifications(self):
        """Summary should work even without certification data."""
        runs = [
            _make_run("r1", ["a"], "completed"),
            _make_run("r2", ["a"], "failed", "timeout"),
        ]
        summary = summarize_operational_memory(runs)

        assert summary["total_runs"] == 2
        assert summary["certification_health"] is None

    def test_operational_memory_demonstrates_value(self):
        """
        Ω-4B value proposition: patterns invisible to single-run analysis.
        """
        # Create 20 runs with a clear pattern: timeout recurs 8 times
        random.seed(42)
        runs: List[Dict[str, Any]] = []
        error_types = ["timeout"] * 8 + ["network"] * 4 + ["disk"] * 2
        for i in range(14):
            err = error_types[i]
            runs.append(_make_run(f"om-{i}", ["a", "b"], "failed", err))
        for i in range(14, 20):
            runs.append(_make_run(f"om-{i}", ["a", "b"], "completed"))

        summary = summarize_operational_memory(runs)

        # Pattern should be visible
        assert len(summary["recurring_patterns"]) > 0
        top_pattern = summary["recurring_patterns"][0]
        assert top_pattern["occurrences"] >= 2
        assert "timeout" in top_pattern["signature"]

        # Failure rate should be calculable
        assert summary["failure_rate"] == 14 / 20

        print(
            f"\n[Ω-4B] Operational memory reveals: "
            f"top_pattern={top_pattern['signature']}, "
            f"occurrences={top_pattern['occurrences']}, "
            f"failure_rate={summary['failure_rate']:.0%}"
        )
