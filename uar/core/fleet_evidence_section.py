"""Evidence Pack v2 fleet signal section builder.

D4C-S1.6 — Evidence Pack v2 Fleet Section.

This module produces a reusable markdown section that can be composed into
existing evidence-pack/report pipelines.  It creates no new report pipeline
and stores no additional state.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from uar.core.fleet_linkage import attach_linkage_to_fleet_summary
from uar.core.fleet_signals import build_fleet_signals, build_fleet_summary
from uar.core.trust_engine import compute_trust


def _outcomes_by_recommendation(
    outcomes: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {}
    for outcome in outcomes:
        rec_id = outcome.get("recommendation_id")
        out_type = outcome.get("outcome_type")
        if not rec_id or not out_type:
            continue
        bucket = counts.setdefault(
            str(rec_id), {"resolved": 0, "recurred": 0, "unknown": 0}
        )
        if out_type in bucket:
            bucket[out_type] += 1
    return counts


def _trust_by_type(
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    try:
        trust = compute_trust(outcomes, metadata)
    except Exception:
        return {}
    return {
        str(item.get("type")): item
        for item in trust.get("recommendation_types", [])
        if item.get("type")
    }


def _category_by_recommendation(
    metadata: Iterable[Dict[str, Any]],
) -> Dict[str, str]:
    mapping = {}
    for item in metadata:
        rec_id = item.get("recommendation_id")
        category = item.get("category")
        if rec_id and category:
            mapping[str(rec_id)] = str(category)
    return mapping


def build_fleet_evidence_section(
    records: Iterable[Dict[str, Any]],
    *,
    outcomes: Optional[List[Dict[str, Any]]] = None,
    recommendation_metadata: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[float] = None,
) -> Dict[str, Any]:
    """Build an Evidence Pack v2 section for fleet signals.

    Returns a dictionary containing both structured data and markdown so it can
    be reused by current or future evidence pack generators.
    """

    generated = time.time() if generated_at is None else generated_at
    outcome_rows = outcomes or []
    metadata_rows = recommendation_metadata or []
    summary = attach_linkage_to_fleet_summary(
        build_fleet_summary(build_fleet_signals(records))
    )
    outcome_counts = _outcomes_by_recommendation(outcome_rows)
    rec_to_category = _category_by_recommendation(metadata_rows)
    trust_types = _trust_by_type(outcome_rows, metadata_rows)

    lines: List[str] = [
        "## Fleet Signal Evidence",
        "",
        f"Generated at: `{generated}`",
        "",
    ]

    if not summary or summary.get("active_signals", 0) == 0:
        lines.extend([
            "Fleet status: **nominal**",
            "",
            "No fleet signals were detected in the analyzed records.",
        ])
        return {
            "section": "fleet_signal_evidence",
            "generated_at": generated,
            "summary": summary,
            "markdown": "\n".join(lines),
        }

    lines.extend([
        f"Fleet status: **{summary.get('status')}**",
        f"Active signals: **{summary.get('active_signals', 0)}**",
        f"Critical signals: **{summary.get('critical_signals', 0)}**",
        f"Warning signals: **{summary.get('warning_signals', 0)}**",
        "",
    ])

    signals = summary.get("signals") or []
    for index, signal in enumerate(signals, start=1):
        linkage = signal.get("linkage") or {}
        replay = linkage.get("replay") or {}
        rec_ids = linkage.get("recommendations") or []
        incident_ids = linkage.get("incidents") or []
        evidence_refs = linkage.get("evidence_refs") or []
        message = signal.get("message") or "No message provided"
        lines.extend([
            f"### {index}. {signal.get('title', 'Fleet signal')}",
            "",
            f"- Level: `{signal.get('level')}`",
            f"- Scope: `{signal.get('scope')}`",
            f"- Message: {message}",
            f"- Latest replay run: `{replay.get('run_id') or 'none'}`",
            f"- Replay available: `{replay.get('available', False)}`",
            f"- Incidents: `{', '.join(incident_ids) if incident_ids else 'none'}`",
            f"- Evidence refs: `{', '.join(evidence_refs) if evidence_refs else 'none'}`",
        ])

        if rec_ids:
            lines.append("- Recommendation outcomes:")
            for rec_id in rec_ids:
                counts = outcome_counts.get(
                    rec_id, {"resolved": 0, "recurred": 0, "unknown": 0}
                )
                category = rec_to_category.get(rec_id, "unknown")
                trust = trust_types.get(category)
                trust_text = (
                    f"trust={trust.get('trust_score')}"
                    if trust else "trust=unavailable"
                )
                lines.append(
                    "  - "
                    f"`{rec_id}` category=`{category}` "
                    f"resolved={counts['resolved']} "
                    f"recurred={counts['recurred']} "
                    f"unknown={counts['unknown']} "
                    f"{trust_text}"
                )
        else:
            lines.append("- Recommendation outcomes: `none linked`")
        lines.append("")

    return {
        "section": "fleet_signal_evidence",
        "generated_at": generated,
        "summary": summary,
        "outcome_counts": outcome_counts,
        "trust_by_type": trust_types,
        "markdown": "\n".join(lines),
    }


__all__ = ["build_fleet_evidence_section"]
