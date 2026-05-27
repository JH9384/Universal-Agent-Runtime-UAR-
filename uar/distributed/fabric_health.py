from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class FabricHealth:
    synchronization_confidence: float
    anomaly_count: int
    missing_replays: int
    repair_backlog: int

    def overall_score(self) -> float:
        penalty = (
            self.anomaly_count * 0.1
            + self.missing_replays * 0.05
            + self.repair_backlog * 0.05
        )
        return max(0.0, min(1.0, self.synchronization_confidence - penalty))

    def to_dict(self) -> Dict[str, object]:
        return {
            "synchronization_confidence": self.synchronization_confidence,
            "anomaly_count": self.anomaly_count,
            "missing_replays": self.missing_replays,
            "repair_backlog": self.repair_backlog,
            "overall_score": self.overall_score(),
        }
