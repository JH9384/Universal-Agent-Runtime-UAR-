"""Certification Engine for UAR.

Converts runtime evidence into operator trust by combining T1 Replay
Confidence, T2 Runtime Health, and T3 Burn-In scores into a
certification level and score.

Issue #87: removed legacy contract_compliance dimension and aligned
weights with Trust Spine evidence model:
    Replay Confidence  40%
    Burn-In            35%
    Runtime Health     25%

Trust Spine Phase: T4
Issues: #57, #70, #87
Spec: docs/CERTIFICATION_MODEL.md
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class CertificationReport:
    """Certification report for a UAR runtime build.

    score is 0-100 weighted composite.
    level is one of: Experimental | Silver | Gold
    evidence summarizes the input scores used.
    """

    score: int
    level: str
    evidence: Dict[str, Any]
    violations: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable report."""
        return asdict(self)


def certification_level(
    score: int,
    replay_score: int,
    burnin_passed: bool,
    burnin_score: int,
    has_violations: bool,
    burnin_ran: bool = False,
) -> str:
    """Derive certification level from composite score and evidence.

    Gold:         score >= 95, replay >= 95, burn-in passed, no violations
    Silver:       score >= 80, replay >= 80, no violations
    Experimental: everything else

    Gold requires burn-in completion; Silver does not, so a fresh
    runtime with strong replay and health scores can still achieve
    operator confidence without a burn-in history.
    """
    if (
        score >= 95
        and replay_score >= 95
        and burnin_passed
        and burnin_ran
        and not has_violations
    ):
        return "Gold"
    if score >= 80 and replay_score >= 80 and not has_violations:
        return "Silver"
    return "Experimental"


def certify_runtime(
    replay_confidence_score: Optional[int] = None,
    burnin_report: Optional[Any] = None,
    runtime_health_score: Optional[int] = None,
) -> CertificationReport:
    """Compute a certification report from T1, T2, and T3 evidence.

    Issue #87: contract_compliance removed.  Pure Trust Spine evidence.

    Args:
        replay_confidence_score: 0-100 score from T1. Defaults to 0.
        burnin_report:           BurnInProxy from T3, or None.
        runtime_health_score:    0-100 score from T2. Defaults to 75
                                 (unknown) when None.

    Returns:
        CertificationReport with score, level, and evidence.

    Weights (Issue #87 — Trust Spine model):
        Replay Confidence  40%
        Burn-In            35%
        Runtime Health     25%
    """
    violations: List[str] = []

    rc_score = 0
    if replay_confidence_score is not None:
        try:
            rc_score = int(round(float(replay_confidence_score)))
        except (TypeError, ValueError):
            violations.append(
                "replay_confidence: non-numeric score; using 0"
            )
    else:
        violations.append("replay_confidence: no score available")

    bi_score = 0
    bi_passed = False
    if burnin_report is not None:
        try:
            bi_score = int(round(float(burnin_report.score)))
            bi_passed = bool(burnin_report.passed)
        except (TypeError, ValueError, AttributeError) as exc:
            violations.append(f"burnin: parse error: {exc}")

    rh_score = 75
    if runtime_health_score is not None:
        try:
            rh_score = int(round(float(runtime_health_score)))
        except (TypeError, ValueError):
            violations.append(
                "runtime_health: non-numeric score; using default"
            )
    else:
        violations.append("runtime_health: no score available; using default")

    if burnin_report is not None:
        weighted = (
            rc_score * 0.40
            + bi_score * 0.35
            + rh_score * 0.25
        )
    else:
        # Redistribute burn-in weight proportionally so a fresh
        # runtime without burn-in history can still reach Silver.
        total = 0.40 + 0.25
        weighted = rc_score * (0.40 / total) + rh_score * (
            0.25 / total
        )
    score = int(round(max(0.0, min(100.0, weighted))))

    level = certification_level(
        score=score,
        replay_score=rc_score,
        burnin_passed=bi_passed,
        burnin_score=bi_score,
        has_violations=bool(violations),
        burnin_ran=burnin_report is not None,
    )

    evidence = {
        "replay_confidence_score": rc_score,
        "burnin_score": bi_score,
        "burnin_passed": bi_passed,
        "runtime_health_score": rh_score,
        "weights": {
            "replay_confidence": 0.40,
            "burnin": 0.35,
            "runtime_health": 0.25,
        },
    }

    return CertificationReport(
        score=score,
        level=level,
        evidence=evidence,
        violations=violations,
        timestamp=time.time(),
    )


__all__ = [
    "CertificationReport",
    "certification_level",
    "certify_runtime",
]
