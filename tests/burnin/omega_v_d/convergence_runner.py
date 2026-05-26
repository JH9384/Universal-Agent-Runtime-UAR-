from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from uar.continuity.feedback_stabilization import FeedbackStabilizationEngine
from uar.restoration.equilibrium import RestorationEquilibriumEngine


@dataclass(slots=True)
class ConvergenceRunResult:
    iterations: int
    minimum_score: float
    final_score: float
    passed: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "iterations": self.iterations,
            "minimum_score": self.minimum_score,
            "final_score": self.final_score,
            "passed": self.passed,
        }


class OmegaVDConvergenceRunner:
    def run(self, iterations: int = 10, threshold: float = 0.25) -> ConvergenceRunResult:
        feedback = FeedbackStabilizationEngine()
        restoration = RestorationEquilibriumEngine()
        minimum_score = 1.0
        final_score = 0.0

        for index in range(iterations):
            restoration_state = restoration.evaluate(
                queue_depth=index % 4,
                repair_pressure=0.2,
                restoration_confidence=0.85,
                completed_repairs=["r1", "r2"],
            )
            feedback_state = feedback.evaluate(
                anomaly_pressure=0.1,
                restoration_velocity=restoration_state.repair_velocity,
                dampening_factor=0.9,
                convergence_pressure=0.1,
            )
            final_score = min(
                restoration_state.equilibrium_score(),
                feedback_state.equilibrium_score(),
            )
            minimum_score = min(minimum_score, final_score)

        return ConvergenceRunResult(
            iterations=iterations,
            minimum_score=minimum_score,
            final_score=final_score,
            passed=minimum_score >= threshold,
        )


def test_omega_v_d_convergence_runner() -> None:
    result = OmegaVDConvergenceRunner().run(iterations=5, threshold=0.2)

    assert result.passed
    assert result.minimum_score >= 0.2
