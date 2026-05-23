"""Canonical RuntimeEvent construction helpers.

These helpers keep event dictionaries schema-stable while the rest of the
runtime still consumes plain dict objects. They are intentionally lightweight:
all emitted events remain JSON-serializable and compatible with replay.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time
from typing import Any

EVENT_SCHEMA_VERSION = "uar.event.v1"


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
    event_type: str,
    *,
    run_id: str,
    goal_id: str,
    skill: str | None = None,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Build a schema-valid RuntimeEvent dictionary."""

    return RuntimeEvent(
        schema_version=EVENT_SCHEMA_VERSION,
        type=event_type,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        timestamp=time() if timestamp is None else timestamp,
        payload=payload or {},
        error=error,
    ).to_dict()


def emit_start(
    *,
    run_id: str,
    goal_id: str,
    skills: list[str],
    timestamp: float | None = None,
) -> dict[str, Any]:
    return make_event(
        "start",
        run_id=run_id,
        goal_id=goal_id,
        payload={"skills": skills},
        timestamp=timestamp,
    )


def emit_skill_start(
    *,
    run_id: str,
    goal_id: str,
    skill: str,
    timestamp: float | None = None,
) -> dict[str, Any]:
    return make_event(
        "skill_start",
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        timestamp=timestamp,
    )


def emit_skill_complete(
    *,
    run_id: str,
    goal_id: str,
    skill: str,
    result: Any,
    timestamp: float | None = None,
) -> dict[str, Any]:
    return make_event(
        "skill_complete",
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        payload={"result": result},
        timestamp=timestamp,
    )


def emit_error(
    *,
    run_id: str,
    goal_id: str,
    error: str,
    skill: str | None = None,
    timestamp: float | None = None,
) -> dict[str, Any]:
    return make_event(
        "error",
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        error=error,
        payload={"error": error},
        timestamp=timestamp,
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
) -> dict[str, Any]:
    return make_event(
        "complete",
        run_id=run_id,
        goal_id=goal_id,
        payload={
            "status": status,
            "outputs": outputs,
            "errors": errors or [],
            "final_context": final_context or {},
        },
        timestamp=timestamp,
    )
