from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RepairConvergence:
    repair_id: str
    merged_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "repair_id": self.repair_id,
            "merged_actions": list(self.merged_actions),
        }


class RepairConvergenceEngine:
    def converge(self, repair_id: str, chains: List[List[str]]) -> RepairConvergence:
        merged = []
        for chain in chains:
            for action in chain:
                if action not in merged:
                    merged.append(action)

        return RepairConvergence(repair_id=repair_id, merged_actions=merged)
