from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict


@dataclass(slots=True)
class RuntimeObservation:
    timestamp: str
    category: str
    payload: Dict[str, Any]

    @classmethod
    def create(cls, category: str, payload: Dict[str, Any]) -> "RuntimeObservation":
        return cls(
            timestamp=datetime.now(UTC).isoformat(),
            category=category,
            payload=dict(payload),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "payload": self.payload,
        }
