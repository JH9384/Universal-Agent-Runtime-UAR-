from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from uar.core.replay_graph import ReplayGraph


@dataclass(slots=True)
class ReplayTraversalResult:
    visited: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "visited": list(self.visited),
        }


class ReplayGraphTraversal:
    def traverse(self, graph: ReplayGraph, start: str) -> ReplayTraversalResult:
        visited = []

        for edge in graph.edges:
            if edge.source == start:
                visited.append(edge.target)

        return ReplayTraversalResult(visited=visited)
