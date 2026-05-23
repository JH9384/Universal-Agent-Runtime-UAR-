"""Replay certification helpers.

Certification compares runtime behavior while ignoring volatile fields such as
wall-clock timestamps and generated identifiers when requested.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

VOLATILE_EVENT_KEYS = {"timestamp", "correlation_id"}
VOLATILE_ID_KEYS = {"run_id", "goal_id"}


def normalize_event(
    event: dict[str, Any],
    *,
    strip_timestamps: bool = True,
    strip_correlation_id: bool = True,
    normalize_ids: bool = False,
) -> dict[str, Any]:
    """Return a comparison-safe RuntimeEvent copy."""

    normalized = deepcopy(event)

    if strip_timestamps:
        normalized.pop("timestamp", None)
    if strip_correlation_id:
        normalized.pop("correlation_id", None)
    if normalize_ids:
        if "run_id" in normalized:
            normalized["run_id"] = "<run_id>"
        if "goal_id" in normalized:
            normalized["goal_id"] = "<goal_id>"

    return normalized


def normalize_trace(
    events: list[dict[str, Any]],
    *,
    strip_timestamps: bool = True,
    strip_correlation_id: bool = True,
    normalize_ids: bool = False,
) -> list[dict[str, Any]]:
    """Normalize a RuntimeEvent trace for deterministic comparison."""

    return [
        normalize_event(
            event,
            strip_timestamps=strip_timestamps,
            strip_correlation_id=strip_correlation_id,
            normalize_ids=normalize_ids,
        )
        for event in events
    ]


def traces_equivalent(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    normalize_ids: bool = False,
) -> bool:
    """Return true when two traces are equivalent after normalization."""

    return normalize_trace(left, normalize_ids=normalize_ids) == normalize_trace(
        right,
        normalize_ids=normalize_ids,
    )
