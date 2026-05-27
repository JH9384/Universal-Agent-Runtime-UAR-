from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuityIssue:
    issue_id: str
    category: str
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "references": list(self.references),
        }


@dataclass(slots=True)
class ContinuityRepairSuggestion:
    issue_id: str
    suggestion: str
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "issue_id": self.issue_id,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


class ContinuityRepairEngine:
    def suggest(self, issue: ContinuityIssue) -> ContinuityRepairSuggestion:
        confidence = 0.5 + min(len(issue.references), 5) * 0.1
        return ContinuityRepairSuggestion(
            issue_id=issue.issue_id,
            suggestion="review-continuity-chain",
            confidence=min(confidence, 1.0),
        )
