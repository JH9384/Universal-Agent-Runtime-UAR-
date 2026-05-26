from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class RestorationConfidence:
    replay_id: str
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "replay_id": self.replay_id,
            "confidence": self.confidence,
        }


class RestorationConfidenceAggregator:
    def aggregate(self, replay_id: str, scores: List[float]) -> RestorationConfidence:
        confidence = sum(scores) / max(len(scores), 1)
        return RestorationConfidence(replay_id=replay_id, confidence=confidence)
