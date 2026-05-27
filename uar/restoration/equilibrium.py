from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class RestorationEquilibrium:
    queue_depth: int
    repair_pressure: float
    restoration_confidence: float
    repair_velocity: float

    def equilibrium_score(self) -> float:
        pressure_penalty = min(1.0, self.repair_pressure * 0.25)
        queue_penalty = min(1.0, self.queue_depth * 0.05)
        velocity_bonus = min(0.25, self.repair_velocity * 0.05)
        return max(
            0.0,
            min(
                1.0,
                self.restoration_confidence - pressure_penalty - queue_penalty + velocity_bonus,
            ),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "queue_depth": self.queue_depth,
            "repair_pressure": self.repair_pressure,
            "restoration_confidence": self.restoration_confidence,
            "repair_velocity": self.repair_velocity,
            "equilibrium_score": self.equilibrium_score(),
        }


class RestorationEquilibriumEngine:
    def evaluate(
        self,
        queue_depth: int,
        repair_pressure: float,
        restoration_confidence: float,
        completed_repairs: List[str],
    ) -> RestorationEquilibrium:
        repair_velocity = len(completed_repairs) / max(queue_depth + len(completed_repairs), 1)
        return RestorationEquilibrium(
            queue_depth=queue_depth,
            repair_pressure=repair_pressure,
            restoration_confidence=restoration_confidence,
            repair_velocity=repair_velocity,
        )
