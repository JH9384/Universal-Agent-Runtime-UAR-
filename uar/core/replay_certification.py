"""Replay certification primitives for UAR runtime governance.

Phase 2B introduces certification as a lightweight, deterministic report
object. The first layer does not replay workloads by itself; it validates event
streams and contract metadata so CI and executor enforcement can converge on a
single certification surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional

from .schema import CURRENT_EVENT_SCHEMA, validate_event


ReplayCertificationStatus = Literal["CERTIFIED", "CONDITIONAL", "FAILED"]


@dataclass(slots=True)
class ReplayCertificationViolation:
    """Single replay certification violation."""

    code: str
    message: str
    event_index: Optional[int] = None
    skill: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReplayCertificationReport:
    """Deterministic replay certification result."""

    status: ReplayCertificationStatus
    schema_version: str = CURRENT_EVENT_SCHEMA
    event_count: int = 0
    violations: List[ReplayCertificationViolation] = field(
        default_factory=list
    )
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def certified(self) -> bool:
        return self.status == "CERTIFIED"

    @property
    def failed(self) -> bool:
        return self.status == "FAILED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "event_count": self.event_count,
            "violations": [
                {
                    "code": item.code,
                    "message": item.message,
                    "event_index": item.event_index,
                    "skill": item.skill,
                    "metadata": item.metadata,
                }
                for item in self.violations
            ],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def certify_event_stream(
    events: Iterable[Dict[str, Any]],
    *,
    require_terminal_event: bool = True,
) -> ReplayCertificationReport:
    """Validate a RuntimeEvent stream for replay certification readiness.

    This first-pass certification checks:
    - schema compatibility
    - required event fields
    - run_id / goal_id consistency
    - presence of terminal complete/error event when required
    - basic event ordering: start must appear before other runtime events
    """
    event_list = list(events)
    violations: List[ReplayCertificationViolation] = []
    warnings: List[str] = []

    seen_start = False
    run_id: Optional[str] = None
    goal_id: Optional[str] = None
    terminal_seen = False

    for index, event in enumerate(event_list):
        for err in validate_event(event):
            violations.append(
                ReplayCertificationViolation(
                    code="EVENT_SCHEMA_INVALID",
                    message=err,
                    event_index=index,
                    skill=event.get("skill") if isinstance(event, dict) else None,
                )
            )

        if not isinstance(event, dict):
            continue

        event_type = event.get("type")
        if event_type == "start":
            if seen_start:
                violations.append(
                    ReplayCertificationViolation(
                        code="DUPLICATE_START_EVENT",
                        message="RuntimeEvent stream contains multiple start events",
                        event_index=index,
                    )
                )
            seen_start = True
        elif not seen_start:
            violations.append(
                ReplayCertificationViolation(
                    code="EVENT_BEFORE_START",
                    message="RuntimeEvent appeared before start event",
                    event_index=index,
                    skill=event.get("skill"),
                )
            )

        if event_type in {"complete", "error"}:
            terminal_seen = True

        current_run_id = event.get("run_id")
        current_goal_id = event.get("goal_id")
        if run_id is None:
            run_id = current_run_id
        elif current_run_id != run_id:
            violations.append(
                ReplayCertificationViolation(
                    code="RUN_ID_DRIFT",
                    message="RuntimeEvent stream contains inconsistent run_id values",
                    event_index=index,
                    metadata={"expected": run_id, "actual": current_run_id},
                )
            )

        if goal_id is None:
            goal_id = current_goal_id
        elif current_goal_id != goal_id:
            violations.append(
                ReplayCertificationViolation(
                    code="GOAL_ID_DRIFT",
                    message="RuntimeEvent stream contains inconsistent goal_id values",
                    event_index=index,
                    metadata={"expected": goal_id, "actual": current_goal_id},
                )
            )

    if not event_list:
        violations.append(
            ReplayCertificationViolation(
                code="EMPTY_EVENT_STREAM",
                message="Replay certification requires at least one event",
            )
        )

    if require_terminal_event and event_list and not terminal_seen:
        warnings.append(
            "RuntimeEvent stream has no terminal complete/error event"
        )

    if violations:
        status: ReplayCertificationStatus = "FAILED"
    elif warnings:
        status = "CONDITIONAL"
    else:
        status = "CERTIFIED"

    return ReplayCertificationReport(
        status=status,
        event_count=len(event_list),
        violations=violations,
        warnings=warnings,
        metadata={"run_id": run_id, "goal_id": goal_id},
    )
