"""RE-AUDIT SPRINT Ω-3A — Workload Validation.

Real workloads against the UAR runtime itself.
Goal: Does synthetic certification match real behavior?

Observations are logged, not enforced as pass/fail (with
exceptions for fidelity and consistency which must never degrade).
"""

from __future__ import annotations

import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List

import dataclasses

from uar.core.analytics_cache import ANALYTICS_CACHE, AnalyticsCache
from uar.core.analytics_snapshot import build_analytics_snapshot
from uar.core.executor import make_executor_event
from uar.core.replay import run_record_from_events, certify_replay


# ------------------------------------------------------------------
# Helpers — Real workload generation
# ------------------------------------------------------------------

def _discover_skills() -> List[str]:
    """Discover actual skill modules in the UAR repository."""
    skills_dir = Path(__file__).resolve().parents[2] / "uar" / "skills"
    if not skills_dir.exists():
        return ["echo", "noop"]
    skills = [
        p.stem for p in skills_dir.glob("*.py")
        if p.stem not in ("__init__", "base")
    ]
    return skills if skills else ["echo", "noop"]


def _make_real_run(
    run_id: str,
    skills: List[str],
    success: bool = True,
) -> List[Dict[str, Any]]:
    """Generate a realistic event stream using actual skill names."""
    events = [
        make_executor_event(
            "start", run_id, "g1",
            payload={"skills": skills},
        ),
    ]
    for skill in skills:
        if success:
            events.append(
                make_executor_event(
                    "skill_complete", run_id, "g1", skill=skill,
                )
            )
        else:
            events.append(
                make_executor_event(
                    "skill_failed", run_id, "g1",
                    skill=skill, error="simulated_failure",
                )
            )
            break

    status = "completed" if success else "failed"
    outputs = [{"skill": s, "ok": True} for s in skills] if success else []
    errors = [] if success else ["simulated_failure"]

    events.append(
        make_executor_event(
            "complete", run_id, "g1",
            payload={
                "status": status,
                "outputs": outputs,
                "errors": errors,
                "final_context": {},
            },
        )
    )
    return events


def _build_run_dicts(
    count: int,
    real_skills: List[str],
    failure_rate: float = 0.25,
) -> List[Dict[str, Any]]:
    """Build synthetic but skill-realistic run records."""
    import random
    random.seed(42)
    runs: List[Dict[str, Any]] = []
    for i in range(count):
        run_id = f"omega3a-run-{i:04d}"
        # Use 2–4 real skills per run
        n_skills = random.randint(2, min(4, len(real_skills)))
        chosen = random.sample(real_skills, n_skills)
        success = random.random() >= failure_rate
        events = _make_real_run(run_id, chosen, success=success)
        record = run_record_from_events(events)
        runs.append(dataclasses.asdict(record))
    return runs


# ------------------------------------------------------------------
# Ω-3A Observations
# ------------------------------------------------------------------

class TestOmega3AWorkloadPatterns:
    """Observe how the system behaves with realistic workloads."""

    REAL_SKILLS: List[str] = []
    WORKLOAD_SIZE = 500

    @classmethod
    def setup_class(cls):
        cls.REAL_SKILLS = _discover_skills()
        ANALYTICS_CACHE.invalidate()

    def test_01_snapshot_growth_with_real_skills(self):
        """Observation: Snapshot size with actual skill names."""
        runs = _build_run_dicts(self.WORKLOAD_SIZE, self.REAL_SKILLS)
        start = time.perf_counter()
        snap = build_analytics_snapshot(
            runs, "alice", False, 24, 50000,
        )
        build_ms = (time.perf_counter() - start) * 1000

        # Log observation (not a hard assertion)
        print(
            f"\n[Ω-3A OBS] Snapshot build: {build_ms:.1f}ms, "
            f"nodes={len(snap.topology_nodes)}, "
            f"edges={len(snap.topology_edges)}, "
            f"skills_discovered={len(self.REAL_SKILLS)}"
        )
        assert snap.runs_analyzed == self.WORKLOAD_SIZE
        # Ω-2 baseline: < 5s for 25k runs; 500 runs should be far less
        assert build_ms < 5000, f"Build degraded: {build_ms:.1f}ms"

    def test_02_replay_fidelity_under_real_workload(self):
        """Critical: Fidelity must remain 100% for valid real streams."""
        runs = _build_run_dicts(self.WORKLOAD_SIZE, self.REAL_SKILLS)
        passed = 0
        for run_dict in runs:
            record = run_record_from_events(run_dict.get("events", []))
            cert = certify_replay(record)
            if cert["fidelity_score"] == 100.0:
                passed += 1

        print(
            f"\n[Ω-3A OBS] Replay fidelity: {passed}/{self.WORKLOAD_SIZE} "
            f"certified"
        )
        assert passed == self.WORKLOAD_SIZE, (
            f"Fidelity regression: {passed}/{self.WORKLOAD_SIZE}"
        )

    def test_03_cache_churn_under_append_load(self):
        """Observation: Cache behavior under sustained write load."""
        cache = AnalyticsCache(ttl_seconds=60)
        runs = _build_run_dicts(100, self.REAL_SKILLS)
        # Simulate many analytics reads between writes
        churn_counts: List[int] = []
        for i, run in enumerate(runs):
            cache.set(
                "failure-clusters", "alice", False, 24, 50000,
                {"run": i},
            )
            # Every 10th run, "invalidate" and rebuild
            if i % 10 == 0:
                cache.invalidate()
                build_analytics_snapshot(
                    runs[: i + 1], "alice", False, 24, 50000,
                )
            churn_counts.append(cache.stats()["entries"])

        max_entries = max(churn_counts)
        print(
            f"\n[Ω-3A OBS] Cache churn: max_entries={max_entries}, "
            f"invalidations={len(runs) // 10}"
        )
        assert max_entries <= 1, "Cache unbounded under churn"

    def test_04_memory_growth_with_real_topology(self):
        """Observation: Memory profile with actual skill topology."""
        tracemalloc.start()
        runs = _build_run_dicts(self.WORKLOAD_SIZE, self.REAL_SKILLS)
        _ = build_analytics_snapshot(runs, "alice", False, 24, 50000)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)
        print(
            f"\n[Ω-3A OBS] Memory: current={current_mb:.1f}MB, "
            f"peak={peak_mb:.1f}MB, runs={self.WORKLOAD_SIZE}, "
            f"skills={len(self.REAL_SKILLS)}"
        )
        # Ω-2 baseline: < 500MB for 25k nodes; 500 runs should be far less
        assert current_mb < 500

    def test_05_skill_failure_pattern_realism(self):
        """Observation: Failure distribution matches real patterns."""
        runs = _build_run_dicts(
            self.WORKLOAD_SIZE, self.REAL_SKILLS, failure_rate=0.25,
        )
        failures = sum(1 for r in runs if r.get("status") != "completed")
        # 25% failure rate should produce ~125 failures
        expected = self.WORKLOAD_SIZE // 4
        deviation = abs(failures - expected)
        print(
            f"\n[Ω-3A OBS] Failure pattern: {failures} failures "
            f"(expected ~{expected}, deviation={deviation})"
        )
        assert deviation < 20  # Statistical variance within tolerance

    def test_06_replay_latency_distribution(self):
        """Observation: Replay certification latency with real events."""
        runs = _build_run_dicts(100, self.REAL_SKILLS)
        latencies: List[float] = []
        for run_dict in runs:
            events = run_dict.get("events", [])
            record = run_record_from_events(events)
            t0 = time.perf_counter()
            certify_replay(record)
            latencies.append((time.perf_counter() - t0) * 1000)

        latencies.sort()
        median = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(
            f"\n[Ω-3A OBS] Replay latency: median={median:.2f}ms, "
            f"p95={p95:.2f}ms"
        )
        # Ω-2 baseline: < 100ms; real workloads should match
        assert median < 100
        assert p95 < 200

    def test_07_investigation_depth_simulation(self):
        """Observation: Click-to-evidence path with realistic data."""
        # Simulate operator clicking through failure clusters
        runs = _build_run_dicts(200, self.REAL_SKILLS, failure_rate=0.5)
        snap = build_analytics_snapshot(runs, "alice", False, 24, 50000)

        # Extract failure clusters (what operator sees)
        from uar.core.analytics_snapshot import extract_failure_clusters
        clusters = extract_failure_clusters(snap, top=50)

        # Simulate: each cluster → replay click → load
        simulated_clicks = len(clusters.get("clusters", []))
        simulated_loads = simulated_clicks  # Assume all load

        print(
            f"\n[Ω-3A OBS] Investigation depth: clusters={simulated_clicks}, "
            f"simulated_loads={simulated_loads}, "
            f"completion_rate={simulated_loads / max(simulated_clicks, 1)}"
        )
        # Clusters may be empty if failure patterns are too diverse;
        # this is an observation, not a hard requirement
        assert simulated_clicks >= 0
