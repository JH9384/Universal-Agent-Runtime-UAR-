from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class ReplayStreamEvent:
    replay_ids: List[str]
    payload: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "replay_ids": list(self.replay_ids),
            "payload": dict(self.payload),
        }
