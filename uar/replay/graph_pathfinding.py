from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from uar.core.replay_graph import ReplayGraph


@dataclass(slots=True)
class ReplayPath:
    nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "nodes": list(self.nodes),
        }


class ReplayGraphPathfinder:
    def find_paths(self, graph: ReplayGraph, source: str) -> ReplayPath:
        nodes = []

        for edge in graph.edges:
            if edge.source == source:
                nodes.append(edge.target)

        return ReplayPath(nodes=nodes)
