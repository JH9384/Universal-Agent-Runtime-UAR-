from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class ContinuityProfile:
    profile_id: str
    category: str
    retention_days: int
    escalation_level: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "category": self.category,
            "retention_days": self.retention_days,
            "escalation_level": self.escalation_level,
        }
