"""Replay scoring helpers for UAR hardening."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayScore:
    total_events: int
    missing_events: int = 0
    duplicate_events: int = 0
    out_of_order_events: int = 0
    invalid_events: int = 0

    def divergence(self) -> float:
        if self.total_events <= 0:
            return 0.0
        raw = (
            self.missing_events
            + self.duplicate_events
            + self.out_of_order_events
            + self.invalid_events
        ) / self.total_events
        return max(0.0, min(1.0, raw))

    def confidence(self) -> float:
        return 1.0 - self.divergence()

    def passes(self, *, minimum_confidence: float = 0.99) -> bool:
        return self.confidence() >= minimum_confidence
