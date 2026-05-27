from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Dict
from uuid import uuid4


@dataclass(slots=True)
class PropagationBudget:
    remaining_depth: int = 3
    remaining_fanout: int = 32

    def exhausted(self) -> bool:
        return self.remaining_depth <= 0 or self.remaining_fanout <= 0

    def consume(self, fanout: int = 1) -> "PropagationBudget":
        return PropagationBudget(
            remaining_depth=max(0, self.remaining_depth - 1),
            remaining_fanout=max(0, self.remaining_fanout - fanout),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "remaining_depth": self.remaining_depth,
            "remaining_fanout": self.remaining_fanout,
        }


@dataclass(slots=True)
class EventEnvelope:
    event_type: str
    payload: Dict[str, object] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time)
    priority_score: int = 5
    ttl_seconds: float = 30.0
    origin_domain: str = "runtime"
    convergence_pressure: float = 0.0
    propagation_budget: PropagationBudget = field(default_factory=PropagationBudget)

    def expired(self, now: float | None = None) -> bool:
        current = time() if now is None else now
        return current - self.timestamp > self.ttl_seconds

    def can_propagate(self) -> bool:
        return not self.expired() and not self.propagation_budget.exhausted()

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "priority_score": self.priority_score,
            "ttl_seconds": self.ttl_seconds,
            "origin_domain": self.origin_domain,
            "convergence_pressure": self.convergence_pressure,
            "propagation_budget": self.propagation_budget.to_dict(),
        }
