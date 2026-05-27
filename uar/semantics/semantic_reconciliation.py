from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from uar.core.semantic_replay import SemanticReplayNormalizer


@dataclass(slots=True)
class SemanticReconciliationResult:
    left: str
    right: str
    equivalent: bool
    score: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "left": self.left,
            "right": self.right,
            "equivalent": self.equivalent,
            "score": self.score,
        }


class SemanticReplayReconciler:
    def __init__(self) -> None:
        self.normalizer = SemanticReplayNormalizer()

    def reconcile(self, left: str, right: str) -> SemanticReconciliationResult:
        left_norm = self.normalizer.normalize(left)
        right_norm = self.normalizer.normalize(right)
        equivalent = left_norm == right_norm

        return SemanticReconciliationResult(
            left=left_norm,
            right=right_norm,
            equivalent=equivalent,
            score=1.0 if equivalent else 0.0,
        )
