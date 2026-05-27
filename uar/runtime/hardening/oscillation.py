"""Oscillation scoring helpers for UAR burn-in."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class OscillationScore:
    samples: tuple[float, ...]

    def amplitude(self) -> float:
        if not self.samples:
            return 0.0
        return max(self.samples) - min(self.samples)

    def direction_changes(self) -> int:
        if len(self.samples) < 3:
            return 0
        changes = 0
        previous = 0
        for left, right in zip(self.samples, self.samples[1:]):
            delta = right - left
            current = 1 if delta > 0 else -1 if delta < 0 else 0
            if current and previous and current != previous:
                changes += 1
            if current:
                previous = current
        return changes

    def normalized(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        baseline = max(abs(mean(self.samples)), 1.0)
        raw = (self.amplitude() / baseline) + (self.direction_changes() / len(self.samples))
        return max(0.0, min(1.0, raw))

    def stable(self, *, threshold: float = 0.25) -> bool:
        return self.normalized() <= threshold
