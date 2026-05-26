from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RepairChain:
    chain_id: str
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "chain_id": self.chain_id,
            "actions": list(self.actions),
        }


class RepairOrchestrator:
    def build_chain(self, issue_id: str) -> RepairChain:
        return RepairChain(
            chain_id=f"repair-{issue_id}",
            actions=[
                "analyze-continuity",
                "reconstruct-replay",
                "validate-restoration",
            ],
        )
