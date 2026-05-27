from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class SyncConfidence:
    identity_id: str
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "identity_id": self.identity_id,
            "confidence": self.confidence,
        }


class SyncConfidenceEstimator:
    def estimate(self, identity_id: str, scores: List[float]) -> SyncConfidence:
        confidence = sum(scores) / max(len(scores), 1)
        return SyncConfidence(identity_id=identity_id, confidence=confidence)
