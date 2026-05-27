from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class RuntimeAlert:
    alert_id: str
    category: str
    severity: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "alert_id": self.alert_id,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
        }
