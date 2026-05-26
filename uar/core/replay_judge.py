"""Replay judge primitive.

Small Phase 3A authority layer that converts replay certification into a
serializable decision for certificates and CI artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .event_hashing import replay_fingerprint
from .replay_certification import certify_event_stream


@dataclass(slots=True)
class ReplayJudgeDecision:
    status: str
    fingerprint: str
    score: float
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "fingerprint": self.fingerprint,
            "score": self.score,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }


def judge_replay(events: List[Dict[str, Any]]) -> ReplayJudgeDecision:
    cert = certify_event_stream(events)
    fingerprint = replay_fingerprint(events)

    if cert.failed:
        return ReplayJudgeDecision(
            status="rejected",
            fingerprint=fingerprint,
            score=0.0,
            reasons=[item.message for item in cert.violations],
            metadata={"certification_status": cert.status},
        )

    if cert.warnings:
        return ReplayJudgeDecision(
            status="conditional",
            fingerprint=fingerprint,
            score=0.75,
            reasons=list(cert.warnings),
            metadata={"certification_status": cert.status},
        )

    return ReplayJudgeDecision(
        status="accepted",
        fingerprint=fingerprint,
        score=1.0,
        reasons=[],
        metadata={"certification_status": cert.status},
    )
