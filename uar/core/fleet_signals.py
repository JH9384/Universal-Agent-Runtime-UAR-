"""Fleet-level operational signals built from existing UAR records.

D4C-S1.1 — Reuse-first Fleet Signal Model.

This module deliberately does **not** introduce a fleet store.  It derives
fleet signals from existing run records, metadata, replay/trust-compatible
identifiers, and operational status fields.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

_FAILURE_STATUSES = {"failed", "error", "cancelled", "timeout"}
_WARNING_STATUSES = {"degraded", "partial", "warning"}

_SCOPE_KEYS = (
    "fleet_node",
    "node_id",
    "node",
    "service",
    "service_id",
    "agent",
    "agent_id",
    "recipe",
)


@dataclass(slots=True)
class FleetSignal:
    """Operator-facing signal derived from existing run evidence."""

    id: str
    level: str
    scope: str
    title: str
    message: str
    affected_run_ids: List[str] = field(default_factory=list)
    latest_run_id: Optional[str] = None
    linked_incident_ids: List[str] = field(default_factory=list)
    linked_recommendation_ids: List[str] = field(default_factory=list)
    trust_delta: Optional[float] = None
    replay_confidence: Optional[float] = None
    evidence_refs: List[str] = field(default_factory=list)
    count: int = 0
    failure_rate: float = 0.0
    updated_at: float = field(default_factory=time.time)

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
    if status in _FAILURE_STATUSES:
        return True
    errors = record.get("errors") or []
    return bool(errors)


def _is_warning(record: Dict[str, Any]) -> bool:
    status = str(record.get("status", "")).lower()
    return status in _WARNING_STATUSES


def _scope_for(record: Dict[str, Any]) -> tuple[str, str]:
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


def _incident_ids(record: Dict[str, Any]) -> List[str]:
    meta = _metadata(record)
    raw = meta.get("incident_ids") or meta.get("incident_id") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(v) for v in raw if v]
    return []


def _recommendation_ids(record: Dict[str, Any]) -> List[str]:
    meta = _metadata(record)
    raw = meta.get("recommendation_ids") or meta.get("recommendation_id") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(v) for v in raw if v]
    return []


def _replay_confidence(record: Dict[str, Any]) -> Optional[float]:
    meta = _metadata(record)
    for key in ("replay_confidence", "replay_score", "confidence"):
        value = meta.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def build_fleet_signals(
    records: Iterable[Dict[str, Any]],
    *,
    min_failures: int = 1,
    now: Optional[float] = None,
) -> List[FleetSignal]:
    """Build fleet signals from existing run records.

    The function groups warning/failure records by existing metadata such as
    node, service, agent, recipe, skill, or goal.  It creates no durable state
    and can be safely reused by Mission Control, alerts, and evidence packs.
    """

    now_ts = time.time() if now is None else now
    groups: Dict[tuple[str, str], Dict[str, Any]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        if not (_is_failure(record) or _is_warning(record)):
            continue

        scope_key, scope_value = _scope_for(record)
        group_key = (scope_key, scope_value)
        group = groups.setdefault(
            group_key,
            {
                "records": [],
                "failures": 0,
                "warnings": 0,
            },
        )
        group["records"].append(record)
        if _is_failure(record):
            group["failures"] += 1
        else:
            group["warnings"] += 1

    signals: List[FleetSignal] = []
    for (scope_key, scope_value), group in groups.items():
        records_for_group = sorted(
            group["records"], key=_record_time, reverse=True
        )
        failures = int(group["failures"])
        warnings = int(group["warnings"])
        total = len(records_for_group)
        if failures < min_failures and warnings == 0:
            continue

        affected_run_ids = [
            str(r.get("run_id")) for r in records_for_group if r.get("run_id")
        ]
        latest_run_id = affected_run_ids[0] if affected_run_ids else None
        failure_rate = failures / total if total else 0.0
        level = (
            "critical" if failures >= 3 or failure_rate >= 0.75 else "warning"
        )
        if failures == 0 and warnings > 0:
            level = "warning"

        linked_incidents: List[str] = []
        linked_recommendations: List[str] = []
        replay_scores: List[float] = []
        evidence_refs: List[str] = []
        for rec in records_for_group:
            linked_incidents.extend(_incident_ids(rec))
            linked_recommendations.extend(_recommendation_ids(rec))
            rc = _replay_confidence(rec)
            if rc is not None:
                replay_scores.append(rc)
            if rec.get("run_id"):
                evidence_refs.append(f"run:{rec['run_id']}")

        replay_confidence = (
            sum(replay_scores) / len(replay_scores) if replay_scores else None
        )
        clean_incidents = list(dict.fromkeys(linked_incidents))
        clean_recommendations = list(dict.fromkeys(linked_recommendations))
        clean_evidence = list(dict.fromkeys(evidence_refs))

        title = f"Fleet signal: {scope_value}"
        if scope_key != "fleet":
            title = (
                f"{scope_key.replace('_', ' ').title()} signal: {scope_value}"
            )

        message = (
            f"{failures} failure(s), {warnings} warning(s) across "
            f"{total} run(s)"
        )

        signals.append(
            FleetSignal(
                id=f"fleet:{scope_key}:{scope_value}",
                level=level,
                scope=scope_key,
                title=title,
                message=message,
                affected_run_ids=affected_run_ids,
                latest_run_id=latest_run_id,
                linked_incident_ids=clean_incidents,
                linked_recommendation_ids=clean_recommendations,
                replay_confidence=replay_confidence,
                evidence_refs=clean_evidence,
                count=total,
                failure_rate=failure_rate,
                updated_at=now_ts,
            )
        )

    priority = {"critical": 0, "warning": 1, "info": 2}
    signals.sort(
        key=lambda s: (
            priority.get(s.level, 2),
            -s.count,
            -(s.failure_rate or 0.0),
            s.title,
        )
    )
    return signals


def build_fleet_summary(signals: Iterable[FleetSignal]) -> Dict[str, Any]:
    """Return a compact Mission Control compatible fleet summary."""

    signal_list = list(signals)
    critical = sum(1 for s in signal_list if s.level == "critical")
    warning = sum(1 for s in signal_list if s.level == "warning")
    status = "critical" if critical else "warning" if warning else "nominal"
    top = signal_list[0].to_dict() if signal_list else None
    return {
        "status": status,
        "active_signals": len(signal_list),
        "critical_signals": critical,
        "warning_signals": warning,
        "top_signal": top,
        "signals": [s.to_dict() for s in signal_list[:5]],
    }


__all__ = ["FleetSignal", "build_fleet_signals", "build_fleet_summary"]
