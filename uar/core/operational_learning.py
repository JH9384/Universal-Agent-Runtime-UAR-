"""Operational Learning for UAR.

Ω-5A: The system uses accumulated knowledge rather than merely storing it.

Not machine learning. Operational learning.

Uses structured data from Ω-4:
- Recurrence patterns
- Recovery paths
- Governance summaries
- Topology evolution

Applies simple, explainable heuristics:
- Frequency ranking
- Success rate weighting
- Threshold alerting
- Trend comparison

Architecture:
    Operational Memory (Ω-4B)
            ↓
    Recommendation Engine (Ω-5A)
            ↓
    Governance Record (Ω-4C)  [enriched]
            ↓
    Operator Dashboard
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uar.core.multi_run_intelligence import (
    FailurePattern,
    RecoveryPath,
    TopologyEvolutionPoint,
)


@dataclass
class Recommendation:
    """A single actionable recommendation for an operator."""

    category: str  # investigate, optimize, review, remediate
    priority: str  # critical, high, medium, low
    confidence: float  # 0.0 - 1.0
    title: str
    description: str
    source: str  # which subsystem generated it
    affected_runs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "priority": self.priority,
            "confidence": round(self.confidence, 2),
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "affected_runs": self.affected_runs,
        }


def recommend_from_recurring_failures(
    patterns: List[FailurePattern],
    min_occurrences: int = 3,
) -> List[Recommendation]:
    """Generate remediation recommendations from recurring failure patterns.

    Heuristic: patterns with more occurrences are more urgent.
    """
    recommendations: List[Recommendation] = []
    for pattern in patterns:
        if pattern.occurrences < min_occurrences:
            continue

        # Confidence scales with frequency
        confidence = min(0.5 + (pattern.occurrences * 0.05), 0.95)

        # Priority based on frequency
        if pattern.occurrences >= 10:
            priority = "critical"
        elif pattern.occurrences >= 5:
            priority = "high"
        else:
            priority = "medium"

        recommendations.append(
            Recommendation(
                category="remediate",
                priority=priority,
                confidence=confidence,
                title=f"Recurring failure: {pattern.signature}",
                description=(
                    f"Pattern '{pattern.signature}' has occurred "
                    f"{pattern.occurrences} times. "
                    f"Consider root cause analysis or configuration change."
                ),
                source="recurrence_engine",
                affected_runs=pattern.affected_runs,
            )
        )

    # Sort by priority then confidence
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(
        key=lambda r: (priority_order.get(r.priority, 4), -r.confidence)
    )
    return recommendations


def recommend_from_recovery_atlas(
    paths: List[RecoveryPath],
    top_n: int = 5,
) -> List[Recommendation]:
    """Generate recovery advice from historical recovery patterns.

    Heuristic: recovery actions with highest success rates are recommended.
    """
    recommendations: List[Recommendation] = []

    # Group by failure signature, find best recovery per signature
    sig_best: Dict[str, RecoveryPath] = {}
    for path in paths:
        if path.outcome == "completed":
            current = sig_best.get(path.failure_signature)
            if current is None or path.success_rate > current.success_rate:
                sig_best[path.failure_signature] = path

    for sig, best in list(sig_best.items())[:top_n]:
        recommendations.append(
            Recommendation(
                category="remediate",
                priority="high" if best.success_rate > 0.7 else "medium",
                confidence=best.success_rate,
                title=f"Recovery path for: {sig}",
                description=(
                    f"Historical recovery success rate: "
                    f"{best.success_rate:.0%} with action "
                    f"'{best.operator_action}'."
                ),
                source="recovery_atlas",
            )
        )

    recommendations.sort(key=lambda r: -r.confidence)
    return recommendations


def recommend_from_topology_evolution(
    points: List[TopologyEvolutionPoint],
) -> List[Recommendation]:
    """Generate optimization signals from topology changes.

    Heuristics:
    - Rapid node growth: investigate skill proliferation
    - Hot region persistence: capacity concern
    - Edge growth outpacing nodes: complexity concern
    """
    if len(points) < 2:
        return []

    recommendations: List[Recommendation] = []
    latest = points[-1]
    earliest = points[0]

    # Node growth rate
    if earliest.total_nodes > 0:
        node_growth = latest.total_nodes / earliest.total_nodes
        if node_growth >= 2.0:
            recommendations.append(
                Recommendation(
                    category="investigate",
                    priority="high",
                    confidence=0.8,
                    title="Topology node growth anomaly",
                    description=(
                        f"Node count grew {node_growth:.1f}x from "
                        f"{earliest.total_nodes} to {latest.total_nodes}. "
                        f"Investigate skill proliferation."
                    ),
                    source="topology_evolution",
                )
            )

    # Edge/node ratio (complexity indicator)
    if latest.total_nodes > 0:
        ratio = latest.total_edges / latest.total_nodes
        if ratio > 20:
            recommendations.append(
                Recommendation(
                    category="optimize",
                    priority="medium",
                    confidence=0.7,
                    title="High edge-to-node ratio",
                    description=(
                        f"Ratio {ratio:.0f}:1 edges to nodes. "
                        f"Consider topology simplification."
                    ),
                    source="topology_evolution",
                )
            )

    # Persistent hot region
    hot_regions = [p.hot_region for p in points if p.hot_region]
    if len(hot_regions) >= 3 and len(set(hot_regions[-3:])) == 1:
        recommendations.append(
            Recommendation(
                category="optimize",
                priority="medium",
                confidence=0.75,
                title=f"Persistent hot region: {hot_regions[-1]}",
                description=(
                    f"Node '{hot_regions[-1]}' has been the most "
                    f"active for {len(hot_regions[-3:])} consecutive periods. "
                    f"Consider capacity review."
                ),
                source="topology_evolution",
            )
        )

    recommendations.sort(key=lambda r: -r.confidence)
    return recommendations


def recommend_from_governance_trends(
    summaries: List[Dict[str, Any]],
) -> List[Recommendation]:
    """Generate governance alerts from trend analysis.

    Heuristics:
    - Approval rate dropping: workload or quality issue
    - Tampered rate increasing: security concern
    - Certification rate dropping: systemic issue
    """
    if len(summaries) < 2:
        return []

    recommendations: List[Recommendation] = []
    current = summaries[-1]
    previous = summaries[-2]

    # Approval rate trend
    curr_approval = current.get("approval_rate", 1.0)
    prev_approval = previous.get("approval_rate", 1.0)
    if prev_approval > 0 and (curr_approval / prev_approval) < 0.8:
        recommendations.append(
            Recommendation(
                category="review",
                priority="high",
                confidence=0.85,
                title="Approval rate declining",
                description=(
                    f"Approval rate dropped from {prev_approval:.0%} "
                    f"to {curr_approval:.0%}. "
                    f"Review operator workload or failure root causes."
                ),
                source="governance_insights",
            )
        )

    # Tampered rate trend
    curr_tampered = current.get("tampered", 0)
    prev_tampered = previous.get("tampered", 0)
    total = current.get("total_records", 1)
    if (
        total > 0
        and curr_tampered / total > 0.1
        and curr_tampered > prev_tampered
    ):
        recommendations.append(
            Recommendation(
                category="investigate",
                priority="critical",
                confidence=0.9,
                title="Tampered detection rate elevated",
                description=(
                    f"{curr_tampered}/{total} records "
                    f"({curr_tampered / total:.0%}) detected as tampered. "
                    f"Investigate data integrity."
                ),
                source="governance_insights",
            )
        )

    # Certification rate trend
    curr_cert = current.get("certification_rate", 1.0)
    prev_cert = previous.get("certification_rate", 1.0)
    if curr_cert < prev_cert and curr_cert < 0.95:
        recommendations.append(
            Recommendation(
                category="investigate",
                priority="high",
                confidence=0.8,
                title="Certification rate declining",
                description=(
                    f"Certification rate dropped from {prev_cert:.0%} "
                    f"to {curr_cert:.0%}. Review event stream quality."
                ),
                source="governance_insights",
            )
        )

    recommendations.sort(key=lambda r: -r.confidence)
    return recommendations


def generate_all_recommendations(
    recurring_patterns: Optional[List[FailurePattern]] = None,
    recovery_paths: Optional[List[RecoveryPath]] = None,
    topology_points: Optional[List[TopologyEvolutionPoint]] = None,
    governance_summaries: Optional[List[Dict[str, Any]]] = None,
) -> List[Recommendation]:
    """Generate a unified recommendation list from all operational sources.

    This is the primary entry point for Ω-5A. It combines inputs from
    all Ω-4 subsystems and produces a prioritized, actionable list.
    """
    all_recs: List[Recommendation] = []

    if recurring_patterns:
        all_recs.extend(recommend_from_recurring_failures(recurring_patterns))

    if recovery_paths:
        all_recs.extend(recommend_from_recovery_atlas(recovery_paths))

    if topology_points:
        all_recs.extend(recommend_from_topology_evolution(topology_points))

    if governance_summaries and len(governance_summaries) >= 2:
        all_recs.extend(
            recommend_from_governance_trends(governance_summaries)
        )

    # Global sort: critical first, then by confidence descending
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_recs.sort(
        key=lambda r: (priority_order.get(r.priority, 4), -r.confidence)
    )

    return all_recs
