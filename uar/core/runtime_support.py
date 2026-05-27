from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeSupportSummary:
    phase: str
    completed: List[str] = field(default_factory=list)
    remaining: List[str] = field(default_factory=list)
    notes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "phase": self.phase,
            "completed": list(self.completed),
            "remaining": list(self.remaining),
            "notes": dict(self.notes),
        }
