from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class ReplayReconciliationResult:
    source_identity: str
    target_identity: str
    shared_replays: List[str]
    missing_from_target: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "source_identity": self.source_identity,
            "target_identity": self.target_identity,
            "shared_replays": list(self.shared_replays),
            "missing_from_target": list(self.missing_from_target),
        }


class ReplayReconciler:
    def reconcile(
        self,
        source_identity: str,
        target_identity: str,
        source_replays: List[str],
        target_replays: List[str],
    ) -> ReplayReconciliationResult:
        source_set = set(source_replays)
        target_set = set(target_replays)

        return ReplayReconciliationResult(
            source_identity=source_identity,
            target_identity=target_identity,
            shared_replays=sorted(source_set & target_set),
            missing_from_target=sorted(source_set - target_set),
        )
