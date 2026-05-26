from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuityHeatmap:
    heatmap_id: str
    nodes: List[str] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "heatmap_id": self.heatmap_id,
            "nodes": list(self.nodes),
            "weights": list(self.weights),
        }
