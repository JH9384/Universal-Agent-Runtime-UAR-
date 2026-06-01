"""Burn-In contracts — evidence and report dataclasses.

Trust Spine Phase: T3
Issue: #62
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class BurnInEvidence:
    """A single scenario result contributing to burn-in evidence."""

    scenario: str
    passed: bool
    detail: str
    score: int


@dataclass(slots=True)
class BurnInReport:
    """Aggregated burn-in evidence report.

    score is 0–100 weighted average of evidence scores.
    passed is True when score >= pass_threshold (default 80).
    """

    level: str
    score: int
    passed: bool
    evidence: List[BurnInEvidence] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable report."""
        return {
            "level": self.level,
            "score": self.score,
            "passed": self.passed,
            "evidence": [asdict(e) for e in self.evidence],
            "errors": list(self.errors),
            "timestamp": self.timestamp,
        }


__all__ = ["BurnInEvidence", "BurnInReport"]
