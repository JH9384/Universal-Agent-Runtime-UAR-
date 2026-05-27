from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class TopologyStreamEvent:
    nodes: List[str]
    links: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "nodes": list(self.nodes),
            "links": list(self.links),
        }
