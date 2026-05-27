from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .replay_restore_point import ReplayRestorePoint


@dataclass(slots=True)
class ReplayRestorationResult:
    restored: bool
    restore_point: ReplayRestorePoint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "restored": self.restored,
            "restore_point": self.restore_point.to_dict(),
        }


class ReplayRestoration:
    """Replay restoration primitives for deterministic continuity."""

    def restore(
        self,
        restore_point: ReplayRestorePoint,
    ) -> ReplayRestorationResult:
        return ReplayRestorationResult(
            restored=True,
            restore_point=restore_point,
        )
