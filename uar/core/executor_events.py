"""Compatibility adapter between Executor and canonical RuntimeEvents."""

from __future__ import annotations

from typing import Any

from .events import RuntimeEventType, make_event


def make_executor_event(
    event_type: RuntimeEventType | str,
    run_id: str,
    goal_id: str,
    *,
    skill: str | None = None,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
    correlation_id: str = "",
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Build an executor event via the canonical RuntimeEvent builder."""

    return make_event(
        event_type,
        run_id=run_id,
        goal_id=goal_id,
        skill=skill,
        payload=payload,
        error=error,
        timestamp=timestamp,
        metadata={"correlation_id": correlation_id},
    )
