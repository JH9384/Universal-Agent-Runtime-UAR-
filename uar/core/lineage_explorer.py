from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class LineageNode:
    node_id: str
    parent_id: str | None = None

    def to_dict(self) -> Dict[str, str | None]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
        }


class LineageExplorer:
    def __init__(self) -> None:
        self.nodes: List[LineageNode] = []

    def add_node(self, node: LineageNode) -> None:
        self.nodes.append(node)

    def snapshot(self) -> List[Dict[str, str | None]]:
        return [node.to_dict() for node in self.nodes]
