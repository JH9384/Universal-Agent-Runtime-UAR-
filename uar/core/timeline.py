"""Replay timeline projection helpers.

These helpers provide a lightweight, UI-safe view over RuntimeEvent streams
without introducing visualization dependencies into the runtime core.
"""

from __future__ import annotations

from typing import Any


TIMELINE_EVENT_TYPES = {
    "start",
    "skill_start",
    "skill_complete",
    "skill_failed",
    "recipe_start",
    "recipe_end",
    "recipe_skipped",
    "metrics",
    "error",
    "complete",
}


def project_timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project RuntimeEvents into a UI-safe replay timeline."""

    timeline = []

    for idx, event in enumerate(events):
        event_type = event.get("type", "unknown")

        if event_type not in TIMELINE_EVENT_TYPES:
            continue

        timeline.append(
            {
                "index": idx,
                "type": event_type,
                "timestamp": event.get("timestamp"),
                "skill": event.get("skill"),
                "error": event.get("error"),
                "payload": event.get("payload", {}),
            }
        )

    return timeline


def summarize_timeline(
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate lightweight replay timeline metrics."""

    skill_starts = 0
    skill_completes = 0
    failures = 0

    for event in timeline:
        event_type = event.get("type")

        if event_type == "skill_start":
            skill_starts += 1
        elif event_type == "skill_complete":
            skill_completes += 1
        elif event_type in {"skill_failed", "error"}:
            failures += 1

    return {
        "event_count": len(timeline),
        "skill_starts": skill_starts,
        "skill_completes": skill_completes,
        "failures": failures,
    }
