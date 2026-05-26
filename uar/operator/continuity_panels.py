from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuityPanel:
    panel_id: str
    metrics: List[str] = field(default_factory=list)
    overlays: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "panel_id": self.panel_id,
            "metrics": list(self.metrics),
            "overlays": list(self.overlays),
        }
