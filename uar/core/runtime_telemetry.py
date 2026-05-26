from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class RuntimeTelemetryEvent:
    category: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "payload": dict(self.payload),
        }


class RuntimeTelemetryBuffer:
    def __init__(self) -> None:
        self.events: List[RuntimeTelemetryEvent] = []

    def emit(self, category: str, payload: Dict[str, Any]) -> RuntimeTelemetryEvent:
        event = RuntimeTelemetryEvent(category=category, payload=dict(payload))
        self.events.append(event)
        return event

    def snapshot(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events]
