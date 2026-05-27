from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class ReplaySnapshot:
    snapshot_id: str
    replay_id: str
    state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "replay_id": self.replay_id,
            "state": dict(self.state),
        }


class ReplaySnapshotStore:
    def __init__(self) -> None:
        self._snapshots: Dict[str, ReplaySnapshot] = {}

    def save(self, snapshot: ReplaySnapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot

    def load(self, snapshot_id: str) -> ReplaySnapshot | None:
        return self._snapshots.get(snapshot_id)
