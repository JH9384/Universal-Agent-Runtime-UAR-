"""Read-only Evidence Pack correlation section builder.

D9C enriches Evidence Pack output with existing recurrence-correlation context.
It does not create outcomes, mutate trust, change recurrence, or persist derived state.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _value(value: Any, fallback: str = "unknown") -> Any:
    return fallback if value is None else value


def build_correlation_evidence_section(
    correlations: Sequence[Mapping[str, Any]] | None,
    *,
    generated_at: float,
) -> dict[str, Any]:
    """Build a read-only Evidence Pack section from correlation records."""
    records = list(correlations or [])

    lines = [
        "## Recurrence Correlation Evidence",
        "",
        "Read-only view of whether outcome capture and trust movement were followed by later recurrence.",
        "",
    ]

    if not records:
        lines.append("- Correlation: `unavailable`")
        return {
            "section": "recurrence_correlation_evidence",
            "available": False,
            "generated_at": generated_at,
            "correlations": [],
            "markdown": "\n".join(lines),
        }

    normalized: list[dict[str, Any]] = []
    for item in records:
        record = {
            "recommendation_id": _value(item.get("recommendation_id")),
            "run_id": _value(item.get("run_id")),
            "outcome_type": _value(item.get("outcome_type")),
            "trust_before": item.get("trust_before"),
            "trust_after": item.get("trust_after"),
            "trust_delta": item.get("trust_delta"),
            "later_recurrence_count": int(item.get("later_recurrence_count") or 0),
            "later_recurrence_run_ids": list(item.get("later_recurrence_run_ids") or []),
            "correlation_status": _value(item.get("correlation_status")),
            "evidence_refs": list(item.get("evidence_refs") or []),
        }
        normalized.append(record)
        lines.extend([
            f"- Recommendation: `{record['recommendation_id']}`",
            f"  - Run: `{record['run_id']}`",
            f"  - Outcome: `{record['outcome_type']}`",
            f"  - Correlation: `{record['correlation_status']}`",
            f"  - Later recurrence count: `{record['later_recurrence_count']}`",
            f"  - Later recurrence runs: `{', '.join(record['later_recurrence_run_ids']) if record['later_recurrence_run_ids'] else 'none'}`",
            f"  - Evidence refs: `{', '.join(record['evidence_refs']) if record['evidence_refs'] else 'none'}`",
        ])

    return {
        "section": "recurrence_correlation_evidence",
        "available": True,
        "generated_at": generated_at,
        "correlations": normalized,
        "markdown": "\n".join(lines),
    }


__all__ = ["build_correlation_evidence_section"]
