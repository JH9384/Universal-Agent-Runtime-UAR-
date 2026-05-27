"""Runtime pressure metrics for UAR hardening burn-in."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class PressureSnapshot:
    """Point-in-time pressure state used by burn-in certification."""

    queue_depth: int = 0
    websocket_backlog: int = 0
    propagation_fanout: int = 0
    mutation_rate: float = 0.0
    replay_latency_ms: float = 0.0
    dropped_events: int = 0
    observer_lag_ms: float = 0.0
    timestamp: float = field(default_factory=monotonic)

    def pressure_score(self) -> float:
        """Return a bounded normalized pressure score in the range [0, 1]."""

        raw = (
            self.queue_depth / 1_000
            + self.websocket_backlog / 1_000
            + self.propagation_fanout / 500
            + self.mutation_rate / 10_000
            + self.replay_latency_ms / 5_000
            + self.dropped_events / 1_000
            + self.observer_lag_ms / 5_000
        ) / 7
        return max(0.0, min(1.0, raw))


@dataclass(frozen=True)
class EquilibriumSnapshot:
    """Convergence and oscillation state for topology/runtime hardening."""

    pressure: PressureSnapshot
    convergence_score: float
    oscillation_score: float
    stabilization_latency_ms: float
    hysteresis_active: bool = False

    def is_stable(self, *, threshold: float = 0.75) -> bool:
        return (
            self.convergence_score >= threshold
            and self.oscillation_score <= (1.0 - threshold)
            and self.pressure.pressure_score() <= (1.0 - threshold)
        )


@dataclass
class PressureLedger:
    """Append-only in-memory ledger for pressure samples."""

    samples: list[PressureSnapshot] = field(default_factory=list)

    def record(self, snapshot: PressureSnapshot) -> PressureSnapshot:
        self.samples.append(snapshot)
        return snapshot

    def latest(self) -> PressureSnapshot | None:
        return self.samples[-1] if self.samples else None

    def max_pressure(self) -> float:
        if not self.samples:
            return 0.0
        return max(sample.pressure_score() for sample in self.samples)

    def summarize(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "sample_count": len(self.samples),
            "max_pressure": self.max_pressure(),
            "latest_pressure": latest.pressure_score() if latest else 0.0,
            "dropped_events": sum(sample.dropped_events for sample in self.samples),
        }
