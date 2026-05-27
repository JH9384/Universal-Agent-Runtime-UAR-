from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ReplayIndexEntry:
    replay_id: str
    certificate_hash: str
    parent_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "replay_id": self.replay_id,
            "certificate_hash": self.certificate_hash,
            "parent_ids": list(self.parent_ids),
        }


class ReplayIndex:
    def __init__(self) -> None:
        self._entries: Dict[str, ReplayIndexEntry] = {}

    def add(self, entry: ReplayIndexEntry) -> None:
        self._entries[entry.replay_id] = entry

    def get(self, replay_id: str) -> ReplayIndexEntry | None:
        return self._entries.get(replay_id)

    def parents(self, replay_id: str) -> List[str]:
        entry = self.get(replay_id)
        return list(entry.parent_ids) if entry else []
