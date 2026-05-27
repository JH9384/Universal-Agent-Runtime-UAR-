from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ConvergedState:
    state_id: str
    participating_domains: List[str] = field(default_factory=list)
    convergence_score: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "state_id": self.state_id,
            "participating_domains": list(self.participating_domains),
            "convergence_score": self.convergence_score,
        }


class ContinuityStateConvergence:
    def converge(self, state_id: str, domains: List[str]) -> ConvergedState:
        score = min(1.0, len(set(domains)) / max(len(domains), 1))

        return ConvergedState(
            state_id=state_id,
            participating_domains=list(domains),
            convergence_score=score,
        )
