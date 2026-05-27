from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class RuntimeBusEvent:
    topic: str
    category: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "category": self.category,
            "payload": dict(self.payload),
        }


class RuntimeEventBus:
    def __init__(self) -> None:
        self.events: List[RuntimeBusEvent] = []

    def publish(self, topic: str, category: str, payload: Dict[str, Any]) -> RuntimeBusEvent:
        event = RuntimeBusEvent(topic=topic, category=category, payload=dict(payload))
        self.events.append(event)
        return event

    def snapshot(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def by_category(self, category: str) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events if event.category == category]
