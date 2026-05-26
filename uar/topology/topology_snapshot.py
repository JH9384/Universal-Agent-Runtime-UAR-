from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class TopologySnapshot:
    topology_id: str
    nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "topology_id": self.topology_id,
            "nodes": list(self.nodes),
        }
