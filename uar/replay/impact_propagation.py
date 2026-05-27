from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ImpactPropagation:
    source: str
    impacted: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "impacted": list(self.impacted),
        }


class ReplayImpactPropagator:
    def propagate(self, source: str, nodes: List[str]) -> ImpactPropagation:
        return ImpactPropagation(source=source, impacted=list(nodes))
