from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ReplayGraphEdge:
    source: str
    target: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "source": self.source,
            "target": self.target,
        }


@dataclass(slots=True)
class ReplayGraph:
    edges: List[ReplayGraphEdge] = field(default_factory=list)

    def connect(self, source: str, target: str) -> None:
        self.edges.append(ReplayGraphEdge(source=source, target=target))

    def to_dict(self) -> Dict[str, object]:
        return {
            "edges": [edge.to_dict() for edge in self.edges],
        }
