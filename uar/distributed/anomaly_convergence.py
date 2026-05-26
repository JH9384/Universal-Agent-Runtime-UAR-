from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class AnomalyConvergence:
    convergence_id: str
    anomaly_ids: List[str] = field(default_factory=list)
    convergence_score: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "convergence_id": self.convergence_id,
            "anomaly_ids": list(self.anomaly_ids),
            "convergence_score": self.convergence_score,
        }


class AnomalyConvergenceEngine:
    def converge(self, convergence_id: str, anomaly_ids: List[str]) -> AnomalyConvergence:
        score = min(1.0, len(set(anomaly_ids)) / max(len(anomaly_ids), 1))
        return AnomalyConvergence(
            convergence_id=convergence_id,
            anomaly_ids=list(anomaly_ids),
            convergence_score=score,
        )
