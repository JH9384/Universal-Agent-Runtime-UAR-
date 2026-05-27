"""Certification report models for UAR operational validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CertificationReport:
    name: str
    runtime_healthy: bool
    replay_confidence: float
    pressure_score: float
    oscillation_score: float
    starvation_detected: bool
    topology_healthy: bool

    def passed(self) -> bool:
        return (
            self.runtime_healthy
            and self.replay_confidence >= 0.99
            and self.pressure_score < 0.75
            and self.oscillation_score < 0.5
            and not self.starvation_detected
            and self.topology_healthy
        )

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed()
        return payload
