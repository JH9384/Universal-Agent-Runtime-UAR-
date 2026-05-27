from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class FabricPanel:
    panel_id: str
    identities: List[str] = field(default_factory=list)
    overall_score: float = 0.0
    anomaly_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "panel_id": self.panel_id,
            "identities": list(self.identities),
            "overall_score": self.overall_score,
            "anomaly_ids": list(self.anomaly_ids),
        }
