from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass(slots=True)
class CertificationDecision:
    passed: bool
    failures: list[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "passed": self.passed,
            "failures": list(self.failures),
        }


class CertificationValidator:
    def validate(self, metrics: Mapping[str, float]) -> CertificationDecision:
        failures: list[str] = []

        if metrics.get("queue_pressure", 0.0) > 1.0:
            failures.append("queue_pressure")
        if metrics.get("topology_stability", 1.0) < 0.25:
            failures.append("topology_stability")
        if metrics.get("sync_entropy", 0.0) > 1.0:
            failures.append("sync_entropy")
        if metrics.get("feedback_dampening", 1.0) < 0.25:
            failures.append("feedback_dampening")
        if metrics.get("convergence_score", 1.0) < 0.25:
            failures.append("convergence_score")

        return CertificationDecision(
            passed=not failures,
            failures=failures,
        )


def test_certification_validator_passes_stable_metrics() -> None:
    decision = CertificationValidator().validate(
        {
            "queue_pressure": 0.2,
            "topology_stability": 0.8,
            "sync_entropy": 0.2,
            "feedback_dampening": 0.8,
            "convergence_score": 0.8,
        }
    )

    assert decision.passed
    assert decision.failures == []
