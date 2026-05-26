from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class FabricControlSurface:
    surface_id: str
    controls: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "controls": list(self.controls),
            "indicators": list(self.indicators),
        }
