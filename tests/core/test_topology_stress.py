"""RE-AUDIT SPRINT Ω-2 — C2: Topology Stress.

Discover the capacity envelope of the analytics snapshot topology system.

Goal: Find the degradation curve, not a pass/fail binary.

Stages:
  T1 — 1,000 nodes / 5,000 edges    (effortless)
  T2 — 10,000 nodes / 50,000 edges  (healthy)
  T3 — 25,000 nodes / 125,000 edges (first slope)
  T4 — 50,000 nodes / 250,000 edges (optimization zone)
  T5 — 100,000 nodes / 500,000 edges (degradation boundary)

Metrics captured:
  snapshot_build_ms    — build_analytics_snapshot duration
  extract_ms           — extract_topology_hot_paths duration
  actual_nodes         — len(snapshot.topology_nodes)
  actual_edges         — len(snapshot.topology_edges)
  node_invocations     — sum of all node.invocations
  edge_transitions     — sum of all edge.transitions
"""

from __future__ import annotations

import random
import time
import tracemalloc
from typing import Any, Dict, List

import pytest

from uar.core.analytics_snapshot import (
    build_analytics_snapshot,
    extract_topology_hot_paths,
)

pytestmark = pytest.mark.performance


def _make_topology_runs(
    nodes: int, edges_target: int, seed: int = 42
) -> List[Dict[str, Any]]:
    """Generate synthetic runs that produce a topology of ~N nodes and
    ~E edges.  Each run has 6 skills, producing 5 edges.  The skill
    selection uses a deterministic pseudo-random walk so edges are
    diverse but reproducible.
    """
    random.seed(seed)
    skills = [f"skill_{i}" for i in range(nodes)]
    runs_needed = edges_target // 5

    runs: List[Dict[str, Any]] = []
    for run_idx in range(runs_needed):
        # 6 unique skills per run for diverse edge generation
        idxs = random.sample(range(nodes), 6)
        run_skills = [skills[idx] for idx in idxs]
        status = "success" if run_idx % 4 != 0 else "failed"
        events = []
        if status == "failed":
            events = [
                {
                    "skill": run_skills[0],
                    "error": "timeout",
                    "type": "error",
                    "timestamp": 1000 + run_idx,
                },
            ]
        runs.append(
            {
                "run_id": f"r{run_idx}",
                "id": f"r{run_idx}",
                "status": status,
                "skills": run_skills,
                "events": events,
                "metadata": {},
                "created_at": 1000 + run_idx,
                "timestamp": 1000 + run_idx,
                "user_id": "alice",
                "user": "alice",
            }
        )
    return runs


def _build_and_extract(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build snapshot + extract hot paths, returning timing and counts."""
    t0 = time.perf_counter()
    snap = build_analytics_snapshot(runs, "alice", False, 24, 50000)
    build_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    result = extract_topology_hot_paths(snap, top=50)
    extract_ms = (time.perf_counter() - t0) * 1000

    return {
        "build_ms": build_ms,
        "extract_ms": extract_ms,
        "actual_nodes": len(snap.topology_nodes),
        "actual_edges": len(snap.topology_edges),
        "node_invocations": sum(
            n.invocations for n in snap.topology_nodes.values()
        ),
        "edge_transitions": sum(
            e.transitions for e in snap.topology_edges.values()
        ),
        "result": result,
        "snap": snap,
    }


# ------------------------------------------------------------------
# T1 — 1,000 nodes / 5,000 edges
# ------------------------------------------------------------------

class TestTopologyStressT1:
    """C2-T1: 1,000 nodes — effortless."""

    NODES = 1000
    EDGES_TARGET = 5000

    def test_build_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["build_ms"] < 500, (
            f"T1 build time {m['build_ms']:.1f}ms exceeds 500ms"
        )

    def test_extract_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["extract_ms"] < 100, (
            f"T1 extract time {m['extract_ms']:.1f}ms exceeds 100ms"
        )

    def test_node_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        # Should populate most nodes
        assert m["actual_nodes"] >= self.NODES * 0.8
        assert m["actual_nodes"] <= self.NODES

    def test_edge_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        # Unique edges may be slightly less than target due to collisions
        assert m["actual_edges"] >= self.EDGES_TARGET * 0.7
        assert m["actual_edges"] <= self.EDGES_TARGET * 1.1

    def test_invocation_counts_consistent(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        # Each run has 6 skills, so total invocations = 6 * runs
        expected_invocations = len(runs) * 6
        assert m["node_invocations"] == expected_invocations

    def test_transition_counts_consistent(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        # Each run has 5 edges, total transitions = 5 * runs
        expected_transitions = len(runs) * 5
        assert m["edge_transitions"] == expected_transitions

    def test_top_nodes_returned(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert len(m["result"]["nodes"]) == 50


# ------------------------------------------------------------------
# T2 — 10,000 nodes / 50,000 edges
# ------------------------------------------------------------------

class TestTopologyStressT2:
    """C2-T2: 10,000 nodes — healthy."""

    NODES = 10000
    EDGES_TARGET = 50000

    def test_build_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["build_ms"] < 2000, (
            f"T2 build time {m['build_ms']:.1f}ms exceeds 2000ms"
        )

    def test_extract_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["extract_ms"] < 500, (
            f"T2 extract time {m['extract_ms']:.1f}ms exceeds 500ms"
        )

    def test_node_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_nodes"] >= self.NODES * 0.8
        assert m["actual_nodes"] <= self.NODES

    def test_edge_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_edges"] >= self.EDGES_TARGET * 0.7
        assert m["actual_edges"] <= self.EDGES_TARGET * 1.1

    def test_top_nodes_returned(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert len(m["result"]["nodes"]) == 50


# ------------------------------------------------------------------
# T3 — 25,000 nodes / 125,000 edges
# ------------------------------------------------------------------

class TestTopologyStressT3:
    """C2-T3: 25,000 nodes — first noticeable slope."""

    NODES = 25000
    EDGES_TARGET = 125000

    def test_build_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["build_ms"] < 5000, (
            f"T3 build time {m['build_ms']:.1f}ms exceeds 5000ms"
        )

    def test_extract_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["extract_ms"] < 2000, (
            f"T3 extract time {m['extract_ms']:.1f}ms exceeds 2000ms"
        )

    def test_node_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_nodes"] >= self.NODES * 0.8
        assert m["actual_nodes"] <= self.NODES

    def test_memory_bounded(self):
        tracemalloc.start()
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        _build_and_extract(runs)
        current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mb = current / (1024 * 1024)
        assert mb < 500, (
            f"T3 memory {mb:.1f}MB exceeds 500MB"
        )


# ------------------------------------------------------------------
# T4 — 50,000 nodes / 250,000 edges
# ------------------------------------------------------------------

class TestTopologyStressT4:
    """C2-T4: 50,000 nodes — optimization zone."""

    NODES = 50000
    EDGES_TARGET = 250000

    def test_build_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["build_ms"] < 10000, (
            f"T4 build time {m['build_ms']:.1f}ms exceeds 10000ms"
        )

    def test_extract_time_under_threshold(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["extract_ms"] < 5000, (
            f"T4 extract time {m['extract_ms']:.1f}ms exceeds 5000ms"
        )

    def test_node_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_nodes"] >= self.NODES * 0.8
        assert m["actual_nodes"] <= self.NODES

    def test_memory_bounded(self):
        tracemalloc.start()
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        _build_and_extract(runs)
        current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mb = current / (1024 * 1024)
        assert mb < 1000, (
            f"T4 memory {mb:.1f}MB exceeds 1000MB"
        )


# ------------------------------------------------------------------
# T5 — 100,000 nodes / 500,000 edges
# ------------------------------------------------------------------

class TestTopologyStressT5:
    """C2-T5: 100,000 nodes — degradation boundary.

    This stage documents behavior rather than enforcing strict pass/fail.
    The test records timing and marks the envelope.
    """

    NODES = 100000
    EDGES_TARGET = 500000

    def test_build_completes(self):
        """The build must finish without crashing."""
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_nodes"] > 0
        assert m["actual_edges"] > 0

    def test_extract_completes(self):
        """The extractor must finish without crashing."""
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert len(m["result"]["nodes"]) <= 50

    def test_node_count_in_range(self):
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["actual_nodes"] >= self.NODES * 0.8
        assert m["actual_nodes"] <= self.NODES

    def test_build_time_documented(self):
        """Record build time for envelope analysis.

        No hard threshold — this is data for the certification report.
        """
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        # If build exceeds 30s, flag as potentially degraded
        assert m["build_ms"] < 30000, (
            f"T5 build time {m['build_ms']:.1f}ms — degradation boundary"
        )

    def test_extract_time_documented(self):
        """Record extract time for envelope analysis."""
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        m = _build_and_extract(runs)
        assert m["extract_ms"] < 15000, (
            f"T5 extract time {m['extract_ms']:.1f}ms — degradation boundary"
        )

    def test_memory_documented(self):
        tracemalloc.start()
        runs = _make_topology_runs(self.NODES, self.EDGES_TARGET)
        _build_and_extract(runs)
        current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mb = current / (1024 * 1024)
        # If memory exceeds 2GB, flag as potentially degraded
        assert mb < 2000, (
            f"T5 memory {mb:.1f}MB — degradation boundary"
        )


# ------------------------------------------------------------------
# Degradation Curve Summary
# ------------------------------------------------------------------

class TestTopologyDegradationCurve:
    """C2: Compare across stages to detect non-linear degradation."""

    def test_build_time_grows_sub_quadratically(self):
        """Build time should grow slower than O(N^2).

        We measure at T1, T2, T3 and verify the ratio of
        time-to-data-size does not explode.
        """
        stages = [
            (1000, 5000),
            (10000, 50000),
            (25000, 125000),
        ]
        times: List[float] = []
        sizes: List[int] = []
        for nodes, edges in stages:
            runs = _make_topology_runs(nodes, edges)
            t0 = time.perf_counter()
            build_analytics_snapshot(runs, "alice", False, 24, 50000)
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
            sizes.append(len(runs))

        # Compute time-per-run for each stage
        ratios = [times[i] / sizes[i] for i in range(len(stages))]
        # The ratio should not grow super-linearly
        # Allow 10x growth from T1 to T3 (sub-quadratic)
        assert ratios[-1] / ratios[0] < 10, (
            f"Build time per run degraded: {ratios}"
        )

    def test_data_integrity_at_all_stages(self):
        """Verify counts remain consistent across all tested scales."""
        for nodes, edges in [
            (1000, 5000),
            (10000, 50000),
            (25000, 125000),
        ]:
            runs = _make_topology_runs(nodes, edges)
            snap = build_analytics_snapshot(runs, "alice", False, 24, 50000)
            expected_invocations = len(runs) * 6
            expected_transitions = len(runs) * 5
            actual_invocations = sum(
                n.invocations for n in snap.topology_nodes.values()
            )
            actual_transitions = sum(
                e.transitions for e in snap.topology_edges.values()
            )
            assert actual_invocations == expected_invocations
            assert actual_transitions == expected_transitions
