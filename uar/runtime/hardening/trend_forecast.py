"""Pressure trend forecasting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class PressureTrend:
    samples: tuple[float, ...]

    def slope(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return (self.samples[-1] - self.samples[0]) / (len(self.samples) - 1)

    def average(self) -> float:
        if not self.samples:
            return 0.0
        return mean(self.samples)

    def escalating(self) -> bool:
        return self.slope() > 0
