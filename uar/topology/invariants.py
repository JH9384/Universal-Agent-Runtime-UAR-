from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class TopologyInvariant:
    mutation_velocity: float
    edge_density: float
    topology_entropy: float
    fragmentation_score: float

    def stable(self) -> bool:
        return (
            self.mutation_velocity <= 1.0
            and self.edge_density <= 1.0
            and self.topology_entropy <= 1.0
            and self.fragmentation_score <= 1.0
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "mutation_velocity": self.mutation_velocity,
            "edge_density": self.edge_density,
            "topology_entropy": self.topology_entropy,
            "fragmentation_score": self.fragmentation_score,
            "stable": self.stable(),
        }
