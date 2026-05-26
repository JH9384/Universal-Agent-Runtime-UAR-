from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .replay_restoration import ReplayRestoration
from .replay_restore_point import ReplayRestorePoint
from .replay_snapshot_store import ReplaySnapshotStore


@dataclass(slots=True)
class ReplayRecoveryResult:
    recovered: bool
    replay_id: str
    snapshot_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovered": self.recovered,
            "replay_id": self.replay_id,
            "snapshot_id": self.snapshot_id,
        }


class ReplayRecovery:
    """Replay recovery orchestration for deterministic continuity."""

    def __init__(self) -> None:
        self.restoration = ReplayRestoration()
        self.snapshot_store = ReplaySnapshotStore()

    def recover(
        self,
        restore_point: ReplayRestorePoint,
    ) -> ReplayRecoveryResult:
        self.restoration.restore(restore_point)

        return ReplayRecoveryResult(
            recovered=True,
            replay_id=restore_point.replay_id,
            snapshot_id=restore_point.snapshot_id,
        )
