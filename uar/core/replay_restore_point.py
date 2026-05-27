from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class ReplayRestorePoint:
    replay_id: str
    snapshot_id: str
    lineage: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "snapshot_id": self.snapshot_id,
            "lineage": list(self.lineage),
            "metadata": dict(self.metadata),
        }
