"""Memory drift tracking for sustained burn-in."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryWindow:
    baseline_mb: float
    current_mb: float

    def drift_mb(self) -> float:
        return self.current_mb - self.baseline_mb

    def drift_ratio(self) -> float:
        if self.baseline_mb <= 0:
            return 0.0
        return self.current_mb / self.baseline_mb

    def healthy(self, *, max_ratio: float = 1.25) -> bool:
        return self.drift_ratio() <= max_ratio
