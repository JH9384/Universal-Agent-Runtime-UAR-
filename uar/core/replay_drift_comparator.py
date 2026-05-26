"""Replay drift comparison engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReplayDriftResult:
    topology_drift: float
    semantic_drift: float
    governance_drift: float

    @property
    def total_drift(self) -> float:
        return (
            self.topology_drift
            + self.semantic_drift
            + self.governance_drift
        ) / 3.0


class ReplayDriftComparator:
    def compare(
        self,
        topology_a: str,
        topology_b: str,
        semantic_a: str,
        semantic_b: str,
        governance_a: str,
        governance_b: str,
    ) -> ReplayDriftResult:
        return ReplayDriftResult(
            topology_drift=0.0 if topology_a == topology_b else 1.0,
            semantic_drift=0.0 if semantic_a == semantic_b else 1.0,
            governance_drift=0.0 if governance_a == governance_b else 1.0,
        )
