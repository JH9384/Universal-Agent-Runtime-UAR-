from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class FeedbackEquilibrium:
    anomaly_pressure: float
    restoration_velocity: float
    dampening_factor: float
    convergence_pressure: float

    def equilibrium_score(self) -> float:
        stabilization = self.restoration_velocity * self.dampening_factor
        instability = self.anomaly_pressure + self.convergence_pressure
        return max(0.0, min(1.0, stabilization - instability + 1.0))

    def to_dict(self) -> Dict[str, object]:
        return {
            "anomaly_pressure": self.anomaly_pressure,
            "restoration_velocity": self.restoration_velocity,
            "dampening_factor": self.dampening_factor,
            "convergence_pressure": self.convergence_pressure,
            "equilibrium_score": self.equilibrium_score(),
        }


class FeedbackStabilizationEngine:
    def evaluate(
        self,
        anomaly_pressure: float,
        restoration_velocity: float,
        dampening_factor: float,
        convergence_pressure: float,
    ) -> FeedbackEquilibrium:
        return FeedbackEquilibrium(
            anomaly_pressure=anomaly_pressure,
            restoration_velocity=restoration_velocity,
            dampening_factor=dampening_factor,
            convergence_pressure=convergence_pressure,
        )
