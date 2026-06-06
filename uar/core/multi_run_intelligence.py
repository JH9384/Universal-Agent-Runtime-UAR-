"""Multi-Run Intelligence for UAR.

Ω-4B: Learn what collections of trustworthy runs can teach
the system about itself.

Moves from:
    Run -> Certification
To:
    Run -> Certification -> History -> Patterns

Capabilities:
- Recurrence Engine: detect recurring failure patterns
- Recovery Atlas: map operator actions to recovery outcomes
- Topology Evolution: track topology changes over time
- Certification Failure Ranking: identify weak points
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from uar.core.analytics_snapshot import AnalyticsSnapshot


@dataclass
class FailurePattern:
    """A recurring failure pattern observed across multiple runs."""

    pattern_id: str
    signature: str
    occurrences: int
    affected_runs: List[str] = field(default_factory=list)
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    recovery_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "pattern_id": self.pattern_id,
            "signature": self.signature,
            "occurrences": self.occurrences,
            "affected_runs": self.affected_runs,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "recovery_rate": self.recovery_rate,
        }
        try:
            from uar.uor.bounded_json import compute_uor_digest
            data["uor_digest"] = compute_uor_digest(data)
        except Exception:
            pass
        return data


@dataclass
class RecoveryPath:
    """A sequence: Failure -> Operator Action -> Recovery Outcome."""

    failure_signature: str
    operator_action: str
    outcome: str
    count: int = 0
    success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "failure_signature": self.failure_signature,
            "operator_action": self.operator_action,
            "outcome": self.outcome,
            "count": self.count,
            "success_rate": self.success_rate,
        }
        try:
            from uar.uor.bounded_json import compute_uor_digest
            data["uor_digest"] = compute_uor_digest(data)
        except Exception:
            pass
        return data


@dataclass
class TopologyEvolutionPoint:
    """A snapshot of topology state at a point in time."""

    timestamp: float
    total_nodes: int
    total_edges: int
    hot_region: Optional[str] = None
    node_growth_rate: float = 0.0
    edge_growth_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "hot_region": self.hot_region,
            "node_growth_rate": self.node_growth_rate,
            "edge_growth_rate": self.edge_growth_rate,
        }


def _extract_failure_signature(run_dict: Dict[str, Any]) -> str:
    """Create a stable signature for a failure pattern."""
    errors = run_dict.get("errors", [])
    if not errors:
        return "no_error"
    # Use the first error as the primary signature
    primary = errors[0] if errors else "unknown"
    # Include skills that were attempted
    skills = run_dict.get("skills", [])
    skills_str = "+".join(skills[:2]) if skills else "none"
    return f"{primary}::{skills_str}"


def find_recurring_failures(
    run_dicts: List[Dict[str, Any]],
    min_occurrences: int = 2,
) -> List[FailurePattern]:
    """Recurrence Engine: detect failure patterns that occur multiple times.

    Args:
        run_dicts: List of run dictionaries.
        min_occurrences: Minimum occurrences to be considered recurring.

    Returns:
        List of FailurePattern objects, sorted by occurrences descending.
    """
    failures: List[Tuple[str, str, float]] = []
    for run in run_dicts:
        if run.get("status") != "completed":
            sig = _extract_failure_signature(run)
            run_id = run.get("run_id", "unknown")
            ts = run.get("created_at", 0.0) or run.get("timestamp", 0.0)
            failures.append((sig, run_id, ts))

    # Group by signature
    sig_groups: Dict[str, List[Tuple[str, float]]] = {}
    for sig, run_id, ts in failures:
        sig_groups.setdefault(sig, []).append((run_id, ts))

    patterns: List[FailurePattern] = []
    for idx, (sig, items) in enumerate(sig_groups.items(), 1):
        if len(items) >= min_occurrences:
            run_ids = [r for r, _ in items]
            tss = [t for _, t in items if t]
            patterns.append(
                FailurePattern(
                    pattern_id=f"fp-{idx:03d}",
                    signature=sig,
                    occurrences=len(items),
                    affected_runs=run_ids,
                    first_seen=min(tss) if tss else None,
                    last_seen=max(tss) if tss else None,
                )
            )

    patterns.sort(key=lambda p: p.occurrences, reverse=True)
    return patterns


def build_recovery_atlas(
    run_dicts: List[Dict[str, Any]],
) -> List[RecoveryPath]:
    """Recovery Atlas: map failure signatures to outcomes.

    Analyzes the relationship between failure types and
    their eventual resolution (completed vs failed).

    Args:
        run_dicts: List of run dictionaries.

    Returns:
        List of RecoveryPath objects ranked by frequency.
    """
    # Count outcomes per failure signature
    sig_outcomes: Dict[str, Counter] = {}
    for run in run_dicts:
        sig = _extract_failure_signature(run)
        status = run.get("status", "unknown")
        sig_outcomes.setdefault(sig, Counter())[status] += 1

    paths: List[RecoveryPath] = []
    for sig, outcomes in sig_outcomes.items():
        total = sum(outcomes.values())
        if total == 0:
            continue
        # Infer operator action from runs sharing this signature
        action = "auto"
        for run in run_dicts:
            if _extract_failure_signature(run) == sig:
                action = run.get("action_taken") or run.get(
                    "operator_action"
                ) or action
                if action != "auto":
                    break
        # For each distinct outcome, create a path
        for outcome, count in outcomes.most_common():
            paths.append(
                RecoveryPath(
                    failure_signature=sig,
                    operator_action=action,
                    outcome=outcome,
                    count=count,
                    success_rate=(count / total) if total else 0.0,
                )
            )

    paths.sort(key=lambda p: p.count, reverse=True)
    return paths


def track_topology_evolution(
    snapshots: List[AnalyticsSnapshot],
    timestamps: Optional[List[float]] = None,
) -> List[TopologyEvolutionPoint]:
    """Topology Evolution Map: track how topology changes over time.

    Args:
        snapshots: List of AnalyticsSnapshot objects in chronological order.
        timestamps: Optional list of timestamps for each snapshot.

    Returns:
        List of TopologyEvolutionPoint objects.
    """
    points: List[TopologyEvolutionPoint] = []
    prev_nodes = 0
    prev_edges = 0

    for i, snap in enumerate(snapshots):
        ts = timestamps[i] if timestamps and i < len(timestamps) else float(i)
        nodes = len(snap.topology_nodes)
        edges = len(snap.topology_edges)

        node_rate = (
            (nodes - prev_nodes) / max(prev_nodes, 1)
            if prev_nodes else 0.0
        )
        edge_rate = (
            (edges - prev_edges) / max(prev_edges, 1)
            if prev_edges else 0.0
        )

        # Find hot region: most active node by invocation count
        hot_region = None
        if snap.topology_nodes:
            hot_node = max(
                snap.topology_nodes.items(),
                key=lambda x: x[1].invocations,
            )
            hot_region = hot_node[0]

        points.append(
            TopologyEvolutionPoint(
                timestamp=ts,
                total_nodes=nodes,
                total_edges=edges,
                hot_region=hot_region,
                node_growth_rate=node_rate,
                edge_growth_rate=edge_rate,
            )
        )
        prev_nodes = nodes
        prev_edges = edges

    return points


def rank_certification_failures(
    certifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Identify which types of certification failures occur most often.

    Args:
        certifications: List of certification result dicts.

    Returns:
        List of failure-ranked entries with count and percentage.
    """
    failures: Counter = Counter()
    total = len(certifications)
    if total == 0:
        return []

    for cert in certifications:
        if cert.get("fidelity_score", 100.0) < 100.0:
            error = cert.get("reconstruction_error", "unknown")
            failures[error] += 1

    results: List[Dict[str, Any]] = []
    for error, count in failures.most_common():
        results.append({
            "error_type": error,
            "count": count,
            "percentage": round(count / total * 100, 1),
        })

    return results


def summarize_operational_memory(
    run_dicts: List[Dict[str, Any]],
    certifications: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate multi-run intelligence into a single summary.

    This is the entry point for operational memory: a high-level
    view of what the system has learned from its history.

    Args:
        run_dicts: List of run dictionaries.
        certifications: Optional list of certification results.

    Returns:
        Dict with keys: total_runs, failure_rate, recurring_patterns,
        recovery_paths, certification_health.
    """
    total = len(run_dicts)
    failures = sum(1 for r in run_dicts if r.get("status") != "completed")
    failure_rate = failures / total if total else 0.0

    recurring = find_recurring_failures(run_dicts, min_occurrences=2)
    recovery = build_recovery_atlas(run_dicts)

    cert_health: Optional[Dict[str, Any]] = None
    if certifications:
        cert_failures = rank_certification_failures(certifications)
        passed = sum(
            1 for c in certifications
            if c.get("fidelity_score", 0.0) == 100.0
        )
        cert_health = {
            "total_certified": passed,
            "total_failed": len(certifications) - passed,
            "certification_rate": (
                passed / len(certifications) if certifications else 0.0
            ),
            "top_failures": cert_failures,
        }

    return {
        "total_runs": total,
        "failure_rate": round(failure_rate, 3),
        "recurring_patterns": [p.to_dict() for p in recurring],
        "recovery_paths": [p.to_dict() for p in recovery[:10]],
        "certification_health": cert_health,
    }
