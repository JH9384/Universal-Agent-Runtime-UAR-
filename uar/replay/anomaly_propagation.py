from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class AnomalyPropagation:
    anomaly_id: str
    impacted_nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "anomaly_id": self.anomaly_id,
            "impacted_nodes": list(self.impacted_nodes),
        }


class AnomalyPropagator:
    def propagate(self, anomaly_id: str, nodes: List[str]) -> AnomalyPropagation:
        return AnomalyPropagation(
            anomaly_id=anomaly_id,
            impacted_nodes=list(nodes),
        )
