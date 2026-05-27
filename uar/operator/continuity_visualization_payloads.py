from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuityVisualizationPayload:
    payload_id: str
    overlays: List[str] = field(default_factory=list)
    nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "payload_id": self.payload_id,
            "overlays": list(self.overlays),
            "nodes": list(self.nodes),
        }
