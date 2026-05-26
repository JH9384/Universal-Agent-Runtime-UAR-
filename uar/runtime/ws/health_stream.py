from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class HealthStreamEvent:
    overall_score: float
    anomaly_count: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "overall_score": self.overall_score,
            "anomaly_count": self.anomaly_count,
        }
