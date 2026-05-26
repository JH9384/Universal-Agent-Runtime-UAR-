from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class TimelineAnalysis:
    replay_ids: List[str] = field(default_factory=list)
    density: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "replay_ids": list(self.replay_ids),
            "density": self.density,
        }


class TimelineAnalyzer:
    def analyze(self, replay_ids: List[str]) -> TimelineAnalysis:
        density = len(replay_ids) / max(len(set(replay_ids)), 1)
        return TimelineAnalysis(replay_ids=replay_ids, density=density)
