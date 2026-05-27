from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class FabricStreamEvent:
    event_type: str
    payload: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_type": self.event_type,
            "payload": dict(self.payload),
        }
