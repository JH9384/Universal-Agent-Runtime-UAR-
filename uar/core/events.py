"""Canonical RuntimeEvent construction helpers.

These helpers keep event dictionaries schema-stable while the rest of the
runtime still consumes plain dict objects. They are intentionally lightweight:
all emitted events remain JSON-serializable and compatible with replay.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from time import time
from typing import Any

EVENT_SCHEMA_VERSION = "uar.event.v1"


class RuntimeEventType(str, Enum):
    ORCHESTRATION_PLAN = "orchestration_plan"
    START = "start"
    SKILL_START = "skill_start"
    SKILL_COMPLETE = "skill_complete"
    SKILL_FAILED = "skill_failed"
    RECIPE_START = "recipe_start"
    RECIPE_END = "recipe_end"
    RECIPE_SKIPPED = "recipe_skipped"
    METRICS = "metrics"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass(frozen=True)
class RuntimeEvent:
    schema_version: str
    type: str
    run_id: str
    goal_id: str
    skill: str | None
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(
    event_type: RuntimeEventType | str,
    *,
    run_id: str,
    goal_id: str,
    skill: str | None = None,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid RuntimeEvent dictionary.

    ``metadata`` is for additive, optional fields such as correlation IDs.
    Consumers must not require metadata fields for replay correctness.
    """

    event = RuntimeEvent(
        schema_version=EVENT_SCHEMA_VERSION,
        type=event_type.value if isinstance(event_type, RuntimeEventType) else event_type,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        timestamp=time() if timestamp is None else timestamp,
        payload=payload or {},
        error=error,
    ).to_dict()
    if metadata:
        event.update(metadata)
    return event


def emit_start(
    *,
    run_id: str,
    goal_id: str,
    skills: list[str],
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(
        RuntimeEventType.START,
        run_id=run_id,
        goal_id=goal_id,
        payload={"skills": skills},
        timestamp=timestamp,
        metadata=metadata,
    )


def emit_skill_start(
    *,
    run_id: str,
    goal_id: str,
    skill: str,
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(
        RuntimeEventType.SKILL_START,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        timestamp=timestamp,
        metadata=metadata,
    )


def emit_skill_complete(
    *,
    run_id: str,
    goal_id: str,
    skill: str,
    result: Any,
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(
        RuntimeEventType.SKILL_COMPLETE,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        payload={"result": result},
        timestamp=timestamp,
        metadata=metadata,
    )


def emit_error(
    *,
    run_id: str,
    goal_id: str,
    error: str,
    skill: str | None = None,
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(
        RuntimeEventType.ERROR,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        error=error,
        payload={"error": error},
        timestamp=timestamp,
        metadata=metadata,
    )


def emit_complete(
    *,
    run_id: str,
    goal_id: str,
    status: str,
    outputs: list[Any],
    errors: list[str] | None = None,
    final_context: dict[str, Any] | None = None,
    timestamp: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(
        RuntimeEventType.COMPLETE,
        run_id=run_id,
        goal_id=goal_id,
        payload={
            "status": status,
            "outputs": outputs,
            "errors": errors or [],
            "final_context": final_context or {},
        },
        timestamp=timestamp,
        metadata=metadata,
    )
