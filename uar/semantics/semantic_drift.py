from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class SemanticDriftResult:
    baseline: str
    candidate: str
    drift_score: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "baseline": self.baseline,
            "candidate": self.candidate,
            "drift_score": self.drift_score,
        }


class SemanticDriftAnalyzer:
    def analyze(self, baseline: str, candidate: str) -> SemanticDriftResult:
        baseline_tokens = set(baseline.lower().split())
        candidate_tokens = set(candidate.lower().split())

        overlap = len(baseline_tokens & candidate_tokens)
        total = max(len(baseline_tokens | candidate_tokens), 1)
        drift = 1.0 - (overlap / total)

        return SemanticDriftResult(
            baseline=baseline,
            candidate=candidate,
            drift_score=drift,
        )
