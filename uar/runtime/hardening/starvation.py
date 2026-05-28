"""Queue starvation scoring for UAR burn-in."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueueSample:
    queue_name: str
    age_ms: float
    depth: int
    serviced_count: int


@dataclass(frozen=True)
class StarvationScore:
    samples: tuple[QueueSample, ...]

    def worst_age_ms(self) -> float:
        if not self.samples:
            return 0.0
        return max(sample.age_ms for sample in self.samples)

    def stalled_queues(
        self, *, max_age_ms: float = 5_000.0
    ) -> tuple[str, ...]:
        return tuple(
            sample.queue_name
            for sample in self.samples
            if (
                sample.depth > 0
                and sample.serviced_count == 0
                and sample.age_ms >= max_age_ms
            )
        )

    def healthy(self, *, max_age_ms: float = 5_000.0) -> bool:
        return not self.stalled_queues(max_age_ms=max_age_ms)
