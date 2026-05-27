"""Mutation fairness scoring for UAR burn-in."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class MutationWindow:
    participant_rates: tuple[float, ...]

    def imbalance(self) -> float:
        if not self.participant_rates:
            return 0.0
        average = mean(self.participant_rates)
        if average <= 0:
            return 0.0
        return (max(self.participant_rates) - min(self.participant_rates)) / average

    def fair(self, *, max_imbalance: float = 0.5) -> bool:
        return self.imbalance() <= max_imbalance
