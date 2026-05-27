from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ReplayArchive:
    archive_id: str
    replay_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "archive_id": self.archive_id,
            "replay_ids": list(self.replay_ids),
        }
