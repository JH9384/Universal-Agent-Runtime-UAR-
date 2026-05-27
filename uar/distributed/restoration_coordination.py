from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RestorationCoordination:
    coordination_id: str
    replay_ids: List[str] = field(default_factory=list)
    participating_nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "coordination_id": self.coordination_id,
            "replay_ids": list(self.replay_ids),
            "participating_nodes": list(self.participating_nodes),
        }


class DistributedRestorationCoordinator:
    def coordinate(
        self,
        coordination_id: str,
        replay_ids: List[str],
        participating_nodes: List[str],
    ) -> RestorationCoordination:
        return RestorationCoordination(
            coordination_id=coordination_id,
            replay_ids=list(replay_ids),
            participating_nodes=list(participating_nodes),
        )
