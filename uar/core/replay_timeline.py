from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class ReplayTimelineEvent:
    replay_id: str
    event_type: str
    timestamp: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "replay_id": self.replay_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
        }


class ReplayTimeline:
    def __init__(self) -> None:
        self.events: List[ReplayTimelineEvent] = []

    def append(self, event: ReplayTimelineEvent) -> None:
        self.events.append(event)

    def snapshot(self) -> List[Dict[str, str]]:
        return [event.to_dict() for event in self.events]
