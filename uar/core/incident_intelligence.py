"""Incident intelligence summary built from existing UAR records.

D4C Phase 3 — Incident Intelligence Loop.

This module detects recurrence and links incident/recommendation/outcome/trust
context without adding a new incident store, dashboard, or trust score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from uar.core.fleet_signals import build_fleet_signals
from uar.core.trust_engine import compute_trust

_SCOPE_KEYS = (
    "service",
    "service_id",
    "fleet_node",
    "node_id",
    "node",
    "agent",
    "agent_id",
    "recipe",
)

_FAILURE_STATUSES = {"failed", "error", "cancelled", "timeout"}


@dataclass(slots=True)
class IncidentIntelligenceItem:
    """Recurring operational pattern derived from existing records."""

    id: str
    scope: str
    value: str
    recurrence_count: int
    affected_run_ids: List[str] = field(default_factory=list)
    latest_run_id: Optional[str] = None
    linked_incident_ids: List[str] = field(default_factory=list)
    linked_recommendation_ids: List[str] = field(default_factory=list)
    outcome_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    trust_by_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    meta = record.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _record_time(record: Dict[str, Any]) -> float:
    for key in ("created_at", "timestamp", "updated_at"):
        value = record.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _is_failure(record: Dict[str, Any]) -> bool:
    status = str(record.get("status", "")).lower()
    return status in _FAILURE_STATUSES or bool(record.get("errors") or [])


def _scope_for(record: Dict[str, Any]) -> Tuple[str, str]:
    meta = _metadata(record)
    for key in _SCOPE_KEYS:
        value = meta.get(key)
        if value:
            return key, str(value)
    skills = record.get("skills") or []
    if isinstance(skills, list) and skills:
        return "skill", str(skills[0])
    goal_id = record.get("goal_id")
    if goal_id:
        return "goal", str(goal_id)
    return "fleet", "default"


def _ids_from_meta(record: Dict[str, Any], singular: str, plural: str) -> List[str]:
    meta = _metadata(record)
    raw = meta.get(plural) or meta.get(singular) or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(v) for v in raw if v]
    return []


def _outcomes_by_recommendation(outcomes: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for outcome in outcomes:
        rec_id = outcome.get("recommendation_id")
        outcome_type = outcome.get("outcome_type")
        if not rec_id or not outcome_type:
            continue
        bucket = result.setdefault(str(rec_id), {"resolved": 0, "recurred": 0, "unknown": 0})
        if outcome_type in bucket:
            bucket[str(outcome_type)] += 1
    return result


def _metadata_by_recommendation(metadata: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result = {}
    for row in metadata:
        rec_id = row.get("recommendation_id")
        if rec_id:
            result[str(rec_id)] = dict(row)
    return result


def _trust_by_type(outcomes: List[Dict[str, Any]], metadata: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    try:
        trust = compute_trust(outcomes, metadata)
    except Exception:
        return {}
    return {
        str(item.get("type")): item
        for item in trust.get("recommendation_types", [])
        if item.get("type")
    }


def build_incident_intelligence_summary(
    records: Iterable[Dict[str, Any]],
    *,
    outcomes: Optional[List[Dict[str, Any]]] = None,
    recommendation_metadata: Optional[List[Dict[str, Any]]] = None,
    min_recurrence: int = 2,
) -> Dict[str, Any]:
    """Build recurrence summary from existing records and outcome data."""

    record_list = [r for r in records if isinstance(r, dict)]
    failure_records = [r for r in record_list if _is_failure(r)]
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for record in failure_records:
        grouped.setdefault(_scope_for(record), []).append(record)

    outcome_rows = outcomes or []
    metadata_rows = recommendation_metadata or []
    outcome_counts = _outcomes_by_recommendation(outcome_rows)
    rec_meta = _metadata_by_recommendation(metadata_rows)
    trust_types = _trust_by_type(outcome_rows, metadata_rows)

    items: List[IncidentIntelligenceItem] = []
    for (scope, value), group_records in grouped.items():
        if len(group_records) < min_recurrence:
            continue
        ordered = sorted(group_records, key=_record_time, reverse=True)
        run_ids = [str(r.get("run_id")) for r in ordered if r.get("run_id")]
        rec_ids: List[str] = []
        incident_ids: List[str] = []
        for record in ordered:
            rec_ids.extend(_ids_from_meta(record, "recommendation_id", "recommendation_ids"))
            incident_ids.extend(_ids_from_meta(record, "incident_id", "incident_ids"))
        rec_ids = list(dict.fromkeys(rec_ids))
        incident_ids = list(dict.fromkeys(incident_ids))
        item_outcomes = {rec_id: outcome_counts.get(rec_id, {"resolved": 0, "recurred": 0, "unknown": 0}) for rec_id in rec_ids}
        item_trust: Dict[str, Dict[str, Any]] = {}
        for rec_id in rec_ids:
            category = rec_meta.get(rec_id, {}).get("category")
            if category and category in trust_types:
                item_trust[str(category)] = trust_types[str(category)]
        items.append(
            IncidentIntelligenceItem(
                id=f"incident:{scope}:{value}",
                scope=scope,
                value=value,
                recurrence_count=len(group_records),
                affected_run_ids=run_ids,
                latest_run_id=run_ids[0] if run_ids else None,
                linked_incident_ids=incident_ids,
                linked_recommendation_ids=rec_ids,
                outcome_counts=item_outcomes,
                trust_by_type=item_trust,
                evidence_refs=[f"run:{run_id}" for run_id in run_ids],
            )
        )

    items.sort(key=lambda item: (-item.recurrence_count, item.scope, item.value))
    fleet_signals = build_fleet_signals(record_list)
    return {
        "status": "active" if items else "nominal",
        "recurring_patterns": len(items),
        "total_failures": len(failure_records),
        "top_pattern": items[0].to_dict() if items else None,
        "patterns": [item.to_dict() for item in items],
        "fleet_signal_count": len(fleet_signals),
    }


__all__ = ["IncidentIntelligenceItem", "build_incident_intelligence_summary"]
