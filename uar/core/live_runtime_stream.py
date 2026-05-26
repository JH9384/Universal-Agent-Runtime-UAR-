from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class LiveRuntimeStreamEvent:
    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "payload": dict(self.payload),
        }


class LiveRuntimeStream:
    def __init__(self) -> None:
        self.events: List[LiveRuntimeStreamEvent] = []

    def publish(self, topic: str, payload: Dict[str, Any]) -> LiveRuntimeStreamEvent:
        event = LiveRuntimeStreamEvent(topic=topic, payload=dict(payload))
        self.events.append(event)
        return event

    def snapshot(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events]
