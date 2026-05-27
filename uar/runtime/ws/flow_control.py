from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List

from uar.runtime.event_contracts import EventEnvelope


@dataclass(slots=True)
class FlowControlState:
    accepted: int = 0
    delayed: int = 0
    expired: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "accepted": self.accepted,
            "delayed": self.delayed,
            "expired": self.expired,
        }


@dataclass(slots=True)
class EventFlowBuffer:
    preferred_depth: int = 2048
    preferred_batch_size: int = 256
    events: Deque[EventEnvelope] = field(default_factory=deque)
    state: FlowControlState = field(default_factory=FlowControlState)

    def submit(self, event: EventEnvelope) -> bool:
        if not event.can_propagate():
            self.state.expired += 1
            return False

        if len(self.events) >= self.preferred_depth:
            self.events.popleft()
            self.state.delayed += 1

        self.events.append(event)
        self.state.accepted += 1
        return True

    def drain(self) -> List[Dict[str, object]]:
        drained: List[Dict[str, object]] = []
        while self.events and len(drained) < self.preferred_batch_size:
            event = self.events.popleft()
            if event.can_propagate():
                drained.append(event.to_dict())
            else:
                self.state.expired += 1
        return drained
