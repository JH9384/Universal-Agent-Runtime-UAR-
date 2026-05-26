from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class BroadcastEnvelope:
    channel: str
    event_type: str
    payload: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "channel": self.channel,
            "event_type": self.event_type,
            "payload": dict(self.payload),
        }


class BroadcastHub:
    def __init__(self) -> None:
        self.events: List[BroadcastEnvelope] = []

    def publish(self, envelope: BroadcastEnvelope) -> None:
        self.events.append(envelope)

    def drain(self) -> List[Dict[str, object]]:
        drained = [event.to_dict() for event in self.events]
        self.events.clear()
        return drained
