from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ReplayTimelineNode:
    replay_id: str
    status: str
    related: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "replay_id": self.replay_id,
            "status": self.status,
            "related": list(self.related),
        }


@dataclass(slots=True)
class ReplayTimelineView:
    nodes: List[ReplayTimelineNode] = field(default_factory=list)

    def add_node(self, node: ReplayTimelineNode) -> None:
        self.nodes.append(node)

    def to_dict(self) -> Dict[str, object]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
        }
