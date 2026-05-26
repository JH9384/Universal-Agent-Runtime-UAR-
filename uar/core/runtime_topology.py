from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class RuntimeTopologyNode:
    node_id: str
    category: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "node_id": self.node_id,
            "category": self.category,
        }


class RuntimeTopology:
    def __init__(self) -> None:
        self.nodes: List[RuntimeTopologyNode] = []

    def add_node(self, node: RuntimeTopologyNode) -> None:
        self.nodes.append(node)

    def snapshot(self) -> List[Dict[str, str]]:
        return [node.to_dict() for node in self.nodes]
