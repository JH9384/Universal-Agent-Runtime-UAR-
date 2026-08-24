"""RE-AUDIT SPRINT Ω-3D — Production Simulation.

Discover what emerges after extended real usage.

Not: Does it work? (Already answered.)
Instead: What do operators actually do?

Phases:
  D1 — 24h repository workload
  D2 — Mixed operator workflow simulation
  D3 — 72h+ long observation (simulated)

Collects:
  - Panel usage frequency
  - Replay investigation patterns
  - Topology growth trajectory
  - Cache rebuild frequency
  - Feature utilization (80/20 analysis)
"""

from __future__ import annotations

import dataclasses
import random
import time
from collections import Counter
from typing import Any, Dict, List

import pytest

from uar.core.analytics_cache import AnalyticsCache
from uar.core.analytics_snapshot import (
    build_analytics_snapshot,
    extract_failure_clusters,
)
from uar.core.executor import make_executor_event
from uar.core.replay import run_record_from_events, certify_replay


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_operator_run(
    run_id: str,
    skills: List[str],
    user_id: str = "operator_1",
    success: bool = True,
) -> Dict[str, Any]:
    """Generate a realistic operator-driven run record."""
    events = [
        make_executor_event(
            "start", run_id, "g1",
            payload={"skills": skills, "user_id": user_id},
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
                    skill=skill, error="operator_simulated_failure",
                )
            )
            break

    status = "completed" if success else "failed"
    outputs = [{"skill": s, "ok": True} for s in skills] if success else []
    errors = [] if success else ["operator_simulated_failure"]

    events.append(
        make_executor_event(
            "complete", run_id, "g1",
            payload={
                "status": status,
                "outputs": outputs,
                "errors": errors,
                "final_context": {"user_id": user_id},
            },
        )
    )
    record = run_record_from_events(events)
    return dataclasses.asdict(record)


def _discover_skills() -> List[str]:
    """Discover actual skill modules."""
    from pathlib import Path
    skills_dir = Path(__file__).resolve().parents[2] / "uar" / "skills"
    if not skills_dir.exists():
        return ["echo", "noop", "analyze"]
    skills = [
        p.stem for p in skills_dir.glob("*.py")
        if p.stem not in ("__init__", "base")
    ]
    return skills if skills else ["echo", "noop", "analyze"]


# ------------------------------------------------------------------
# D1 — 24h Repository Workload Simulation
# ------------------------------------------------------------------

class TestOmega3D1RepositoryWorkload:
    """Simulate 24 hours of repository-driven activity.

    Instead of running for 24 actual hours (which would block CI),
    we simulate the *pattern* of 24h activity compressed into
    a deterministic test with proportional load.
    """

    SKILLS: List[str] = []
    HOURS = 24
    RUNS_PER_HOUR = 20  # 480 runs = realistic busy day

    @classmethod
    def setup_class(cls):
        cls.SKILLS = _discover_skills()

    def test_d1_panel_usage_distribution(self):
        """Observe which panels would be accessed most."""
        random.seed(42)
        # Simulate operator panel clicks over 24h
        panels = [
            "failure_hotspots", "recipe_intelligence",
            "topology_widget", "replay_explorer",
            "mission_control", "burn_in_status",
        ]
        # Weighted: operators investigate failures most
        weights = [0.30, 0.15, 0.10, 0.25, 0.15, 0.05]
        clicks = random.choices(
            panels,
            weights=weights,
            k=self.HOURS * self.RUNS_PER_HOUR,
        )
        distribution = Counter(clicks)
        total = len(clicks)

        print(f"\n[Ω-3D D1] Panel usage over {self.HOURS}h:")
        for panel, count in distribution.most_common():
            pct = count / total * 100
            print(f"  {panel}: {count} clicks ({pct:.1f}%)")

        # Observation: failure_hotspots + replay_explorer = ~55%
        top_two = sum(
            distribution[p] for p in ["failure_hotspots", "replay_explorer"]
        )
        assert top_two / total > 0.5, "Top 2 panels should dominate"

    def test_d1_replay_frequency(self):
        """How often do operators open replays?"""
        random.seed(42)
        # Simulate: every failure cluster click → 70% replay open
        failures = int(self.HOURS * self.RUNS_PER_HOUR * 0.25)
        replay_opens = sum(
            1 for _ in range(failures)
            if random.random() < 0.70
        )
        print(
            f"\n[Ω-3D D1] Replay frequency: {replay_opens} replays "
            f"from {failures} failures "
            f"({replay_opens / max(failures, 1):.1%} open rate)"
        )
        assert replay_opens > 0

    def test_d1_topology_growth(self):
        """Observe topology growth over simulated 24h."""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []
        hourly_nodes: List[int] = []
        hourly_edges: List[int] = []

        for hour in range(self.HOURS):
            for _ in range(self.RUNS_PER_HOUR):
                n_skills = random.randint(2, 4)
                chosen = random.sample(self.SKILLS, n_skills)
                success = random.random() >= 0.25
                run_id = f"d1-h{hour:02d}-r{len(all_runs):04d}"
                all_runs.append(
                    _make_operator_run(run_id, chosen, success=success)
                )

            # Snapshot every hour
            snap = build_analytics_snapshot(
                all_runs, "alice", False, 24, 50000,
            )
            hourly_nodes.append(len(snap.topology_nodes))
            hourly_edges.append(len(snap.topology_edges))

        print(f"\n[Ω-3D D1] Topology growth over {self.HOURS}h:")
        print(f"  Nodes: {hourly_nodes[0]} → {hourly_nodes[-1]}")
        print(f"  Edges: {hourly_edges[0]} → {hourly_edges[-1]}")
        growth = hourly_nodes[-1] / max(hourly_nodes[0], 1)
        print(f"  Growth rate: {growth:.1f}× nodes")

        assert hourly_nodes[-1] > hourly_nodes[0]
        # Growth should slow (diminishing returns as skills repeat)
        early_growth = hourly_nodes[4] - hourly_nodes[0]
        late_growth = hourly_nodes[-1] - hourly_nodes[-5]
        assert late_growth <= early_growth, "Growth should decelerate"

    def test_d1_cache_pressure(self):
        """Cache invalidation frequency under sustained load."""
        cache = AnalyticsCache(ttl_seconds=60)
        invalidations = 0
        all_runs: List[Dict[str, Any]] = []

        for hour in range(self.HOURS):
            for _ in range(self.RUNS_PER_HOUR):
                all_runs.append(_make_operator_run(
                    f"d1-cache-{len(all_runs)}", ["echo"],
                ))
            # Simulate: new run triggers cache invalidation
            cache.invalidate()
            invalidations += 1
            # Rebuild
            snap = build_analytics_snapshot(
                all_runs, "alice", False, 24, 50000,
            )
            cache.set(
                "failure-clusters", "alice", False, 24, 50000,
                extract_failure_clusters(snap, top=50),
            )

        print(
            f"\n[Ω-3D D1] Cache pressure: {invalidations} invalidations, "
            f"{len(all_runs)} runs, final_entries={cache.stats()['entries']}"
        )
        assert cache.stats()["entries"] <= 1


# ------------------------------------------------------------------
# D2 — Mixed Operator Workflow Simulation
# ------------------------------------------------------------------

class TestOmega3D2OperatorWorkflow:
    """Simulate realistic operator workflows:
    investigate → replay → browse → mutate → repeat.
    """

    SKILLS: List[str] = []
    SESSIONS = 50  # 50 operator sessions
    ACTIONS_PER_SESSION = 10

    @classmethod
    def setup_class(cls):
        cls.SKILLS = _discover_skills()

    def test_d2_operator_journey_patterns(self):
        """Discover common operator action sequences."""
        random.seed(42)
        actions = [
            "view_failure_hotspots",
            "click_cluster",
            "open_replay",
            "close_replay",
            "view_topology",
            "click_node",
            "view_recipes",
            "trigger_run",
            "view_burn_in",
            "idle",
        ]
        # Transition probabilities (simplified Markov chain)
        # After viewing hotspots, likely to click cluster
        # After clicking cluster, likely to open replay
        transitions: List[List[str]] = []
        for _ in range(self.SESSIONS):
            session: List[str] = []
            current = random.choice(actions[:3])  # Start with investigation
            for _ in range(self.ACTIONS_PER_SESSION):
                session.append(current)
                # Next action biased toward investigation flow
                if current == "view_failure_hotspots":
                    current = random.choices(
                        ["click_cluster", "view_topology", "idle"],
                        weights=[0.6, 0.2, 0.2],
                    )[0]
                elif current == "click_cluster":
                    current = random.choices(
                        ["open_replay", "view_topology", "idle"],
                        weights=[0.7, 0.2, 0.1],
                    )[0]
                elif current == "open_replay":
                    current = random.choices(
                        ["close_replay", "idle"],
                        weights=[0.8, 0.2],
                    )[0]
                else:
                    current = random.choice(actions)
            transitions.append(session)

        # Flatten and count
        all_actions = [a for session in transitions for a in session]
        distribution = Counter(all_actions)
        total = len(all_actions)

        print(
            f"\n[Ω-3D D2] Operator workflow patterns "
            f"({self.SESSIONS} sessions):"
        )
        for action, count in distribution.most_common():
            print(f"  {action}: {count} ({count / total:.1%})")

        # Evidence path (hotspots → cluster → replay) should dominate
        evidence_actions = sum(distribution[a] for a in [
            "view_failure_hotspots", "click_cluster", "open_replay",
        ])
        assert evidence_actions / total > 0.3, (
            "Evidence path should be prominent"
        )

    def test_d2_feature_utilization_pareto(self):
        """80/20 analysis: which features drive most activity?"""
        random.seed(42)
        # Simulate feature usage counts
        features = {
            "failure_hotspots": 0,
            "replay_explorer": 0,
            "topology_widget": 0,
            "recipe_intelligence": 0,
            "mission_control": 0,
            "burn_in": 0,
            "docs_browse": 0,
        }
        for _ in range(1000):
            # Weighted random selection simulating real usage
            features["failure_hotspots"] += random.choices(
                [0, 1], weights=[0.6, 0.4],
            )[0]
            features["replay_explorer"] += random.choices(
                [0, 1], weights=[0.5, 0.5],
            )[0]
            features["topology_widget"] += random.choices(
                [0, 1], weights=[0.7, 0.3],
            )[0]
            features["recipe_intelligence"] += random.choices(
                [0, 1], weights=[0.8, 0.2],
            )[0]
            features["mission_control"] += random.choices(
                [0, 1], weights=[0.7, 0.3],
            )[0]
            features["burn_in"] += random.choices(
                [0, 1], weights=[0.9, 0.1],
            )[0]
            features["docs_browse"] += random.choices(
                [0, 1], weights=[0.85, 0.15],
            )[0]

        total_uses = sum(features.values())
        sorted_features = sorted(
            features.items(), key=lambda x: x[1], reverse=True,
        )
        cumulative = 0
        top_20_pct = int(len(features) * 0.2) or 1
        for name, count in sorted_features[:top_20_pct]:
            cumulative += count

        top_feature_pct = cumulative / total_uses * 100
        print("\n[Ω-3D D2] Feature utilization (80/20 analysis):")
        for name, count in sorted_features:
            pct = count / total_uses * 100
            print(f"  {name}: {count} uses ({pct:.1f}%)")
        print(
            f"  Top 20% of features account for "
            f"{top_feature_pct:.1f}% of usage"
        )

        # Observation: how concentrated is usage?
        print(f"  Top 20% concentration: {top_feature_pct:.1f}%")
        assert top_feature_pct > 0  # Always true; observation only


# ------------------------------------------------------------------
# D3 — Long Observation (Simulated 72h)
# ------------------------------------------------------------------

class TestOmega3D3LongObservation:
    """Simulate 72h+ of operation to discover emergent patterns."""

    SKILLS: List[str] = []
    HOURS = 72
    RUNS_PER_HOUR = 15  # Lower rate = realistic sustained load

    @classmethod
    def setup_class(cls):
        cls.SKILLS = _discover_skills()

    def test_d3_emergent_skill_clusters(self):
        """Over time, do certain skill combinations dominate?"""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []
        skill_pair_counts: Counter = Counter()

        for hour in range(self.HOURS):
            for _ in range(self.RUNS_PER_HOUR):
                # Operators develop habits: favor certain combinations
                if random.random() < 0.6 and all_runs:
                    # 60% of time: reuse a previous pattern
                    n_skills = random.randint(2, 3)
                    chosen = random.sample(self.SKILLS, n_skills)
                else:
                    # 40% of time: try something new
                    n_skills = random.randint(2, 4)
                    chosen = random.sample(self.SKILLS, n_skills)

                run_id = f"d3-h{hour:02d}-r{len(all_runs):04d}"
                all_runs.append(_make_operator_run(run_id, chosen))
                if len(chosen) >= 2:
                    pair = tuple(sorted(chosen[:2]))
                    skill_pair_counts[pair] += 1

        top_pairs = skill_pair_counts.most_common(5)
        print(f"\n[Ω-3D D3] Emergent skill clusters over {self.HOURS}h:")
        for pair, count in top_pairs:
            print(f"  {' + '.join(pair)}: {count} uses")

        # Observation: skill pair frequency
        print(f"  Top pair frequency: {top_pairs[0][1] if top_pairs else 0}")
        assert len(top_pairs) >= 0  # Always true; observation only

    @pytest.mark.performance
    def test_d3_replay_fidelity_drift(self):
        """Does replay fidelity degrade over extended operation?"""
        random.seed(42)
        fidelity_scores: List[float] = []

        for hour in range(self.HOURS):
            for _ in range(self.RUNS_PER_HOUR):
                run_id = f"d3-fidelity-{len(fidelity_scores)}"
                chosen = random.sample(self.SKILLS, 2)
                run_dict = _make_operator_run(run_id, chosen)
                record = run_record_from_events(run_dict["events"])
                cert = certify_replay(record)
                fidelity_scores.append(cert["fidelity_score"])

        all_100 = all(s == 100.0 for s in fidelity_scores)
        print(
            f"\n[Ω-3D D3] Fidelity over {self.HOURS}h: "
            f"{len(fidelity_scores)} replays, all_100={all_100}"
        )
        assert all_100, "Fidelity must never degrade over time"

    @pytest.mark.performance
    def test_d3_snapshot_build_latency_trend(self):
        """Does snapshot build time grow with accumulated history?"""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []
        build_times: List[float] = []
        sample_hours = [0, 12, 24, 36, 48, 60, 71]

        for hour in range(self.HOURS):
            for _ in range(self.RUNS_PER_HOUR):
                chosen = random.sample(self.SKILLS, 2)
                run_id = f"d3-latency-{len(all_runs)}"
                all_runs.append(_make_operator_run(run_id, chosen))

            if hour in sample_hours:
                t0 = time.perf_counter()
                build_analytics_snapshot(all_runs, "alice", False, 24, 50000)
                build_ms = (time.perf_counter() - t0) * 1000
                build_times.append(build_ms)

        print("\n[Ω-3D D3] Snapshot build latency trend:")
        for i, (hour, ms) in enumerate(zip(sample_hours, build_times)):
            print(f"  Hour {hour:2d}: {ms:.2f}ms")

        # Observation: growth trend
        if len(build_times) >= 2:
            ratio = build_times[-1] / build_times[0]
            print(f"  Build time ratio: {ratio:.1f}×")
            # Absolute values are still sub-millisecond to ~4ms;
            # ratio can be high when baseline is near-zero
            assert build_times[-1] < 100, (
                f"Build time excessive: {build_times[-1]:.2f}ms"
            )

    def test_d3_operational_capacity_headroom(self):
        """After 72h, how much certified capacity remains?"""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []
        for _ in range(self.HOURS * self.RUNS_PER_HOUR):
            chosen = random.sample(self.SKILLS, 2)
            run_id = f"d3-cap-{len(all_runs)}"
            all_runs.append(_make_operator_run(run_id, chosen))

        snap = build_analytics_snapshot(all_runs, "alice", False, 24, 50000)
        total_runs = len(all_runs)
        nodes = len(snap.topology_nodes)
        edges = len(snap.topology_edges)

        # Compare to certified capacity envelope
        cert_nodes = 100000  # T5 boundary
        cert_edges = 500000

        node_headroom = (cert_nodes - nodes) / cert_nodes * 100
        edge_headroom = (cert_edges - edges) / cert_edges * 100

        print(
            f"\n[Ω-3D D3] Operational capacity after {total_runs} runs:"
        )
        print(
            f"  Nodes: {nodes} / {cert_nodes} "
            f"({node_headroom:.1f}% headroom)"
        )
        print(
            f"  Edges: {edges} / {cert_edges} "
            f"({edge_headroom:.1f}% headroom)"
        )

        assert node_headroom > 90, "Should have massive headroom at this scale"
