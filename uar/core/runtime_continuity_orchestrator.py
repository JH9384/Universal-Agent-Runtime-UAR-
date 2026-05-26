from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuityCheckpoint:
    checkpoint_id: str
    category: str
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "category": self.category,
            "references": list(self.references),
        }


class RuntimeContinuityOrchestrator:
    def __init__(self) -> None:
        self.checkpoints: Dict[str, ContinuityCheckpoint] = {}

    def add_checkpoint(self, checkpoint: ContinuityCheckpoint) -> None:
        self.checkpoints[checkpoint.checkpoint_id] = checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> ContinuityCheckpoint | None:
        return self.checkpoints.get(checkpoint_id)

    def snapshot(self) -> Dict[str, object]:
        return {
            key: checkpoint.to_dict()
            for key, checkpoint in self.checkpoints.items()
        }
