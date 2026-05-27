from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class TopologyOverlay:
    overlay_id: str
    nodes: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "overlay_id": self.overlay_id,
            "nodes": list(self.nodes),
            "links": list(self.links),
        }
