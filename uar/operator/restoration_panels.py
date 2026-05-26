from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RestorationPanel:
    panel_id: str
    replay_ids: List[str] = field(default_factory=list)
    confidence_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "panel_id": self.panel_id,
            "replay_ids": list(self.replay_ids),
            "confidence_scores": list(self.confidence_scores),
        }
