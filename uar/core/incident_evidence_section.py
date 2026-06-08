"""Evidence Pack v2 incident intelligence section builder.

D4C Phase 3 support layer.

This module composes incident intelligence into evidence output without
creating a new incident report pipeline or durable incident store.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from uar.core.incident_intelligence import build_incident_intelligence_summary


def build_incident_evidence_section(
    records: Iterable[Dict[str, Any]],
    *,
    outcomes: Optional[List[Dict[str, Any]]] = None,
    recommendation_metadata: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[float] = None,
    min_recurrence: int = 2,
) -> Dict[str, Any]:
    """Build markdown and structured data for incident recurrence evidence."""

    generated = time.time() if generated_at is None else generated_at
    summary = build_incident_intelligence_summary(
        records,
        outcomes=outcomes or [],
        recommendation_metadata=recommendation_metadata or [],
        min_recurrence=min_recurrence,
    )

    lines: List[str] = [
        "## Incident Intelligence Evidence",
        "",
        f"Generated at: `{generated}`",
        "",
        f"Status: **{summary.get('status')}**",
        f"Recurring patterns: **{summary.get('recurring_patterns', 0)}**",
        f"Total failures: **{summary.get('total_failures', 0)}**",
        "",
    ]

    patterns = summary.get("patterns") or []
    if not patterns:
        lines.append("No recurring incident patterns were detected.")
        return {
            "section": "incident_intelligence_evidence",
            "generated_at": generated,
            "summary": summary,
            "markdown": "\n".join(lines),
        }

    for index, pattern in enumerate(patterns, start=1):
        rec_ids = pattern.get("linked_recommendation_ids") or []
        incident_ids = pattern.get("linked_incident_ids") or []
        evidence_refs = pattern.get("evidence_refs") or []
        outcome_counts = pattern.get("outcome_counts") or {}
        trust_by_type = pattern.get("trust_by_type") or {}
        lines.extend([
            f"### {index}. {pattern.get('scope')}:{pattern.get('value')}",
            "",
            f"- Recurrence count: `{pattern.get('recurrence_count')}`",
            f"- Latest run: `{pattern.get('latest_run_id') or 'none'}`",
            f"- Affected runs: `{', '.join(pattern.get('affected_run_ids') or []) or 'none'}`",
            f"- Incident IDs: `{', '.join(incident_ids) if incident_ids else 'none'}`",
            f"- Recommendation IDs: `{', '.join(rec_ids) if rec_ids else 'none'}`",
            f"- Evidence refs: `{', '.join(evidence_refs) if evidence_refs else 'none'}`",
        ])
        if outcome_counts:
            lines.append("- Outcome counts:")
            for rec_id, counts in outcome_counts.items():
                lines.append(
                    "  - "
                    f"`{rec_id}` resolved={counts.get('resolved', 0)} "
                    f"recurred={counts.get('recurred', 0)} "
                    f"unknown={counts.get('unknown', 0)}"
                )
        else:
            lines.append("- Outcome counts: `none linked`")
        if trust_by_type:
            lines.append("- Trust movement:")
            for category, trust in trust_by_type.items():
                lines.append(
                    "  - "
                    f"`{category}` trust={trust.get('trust_score')} "
                    f"effectiveness={trust.get('effectiveness_component')}"
                )
        else:
            lines.append("- Trust movement: `unavailable`")
        lines.append("")

    return {
        "section": "incident_intelligence_evidence",
        "generated_at": generated,
        "summary": summary,
        "markdown": "\n".join(lines),
    }


__all__ = ["build_incident_evidence_section"]
