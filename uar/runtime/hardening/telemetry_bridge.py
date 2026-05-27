"""Live telemetry bridge primitives for UAR hardening and operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any

from .operating_modes import OperatingMode, choose_mode
from .oscillation import OscillationScore
from .pressure_metrics import PressureSnapshot
from .replay_score import ReplayScore
from .starvation import StarvationScore


@dataclass(frozen=True)
class RuntimeHealth:
    pressure: float
    oscillation: float
    replay_confidence: float
    starvation: bool
    mode: str
    healthy: bool
    emitted_at: float

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_health(
    *,
    pressure: PressureSnapshot,
    oscillation: OscillationScore,
    replay: ReplayScore,
    starvation: StarvationScore,
) -> RuntimeHealth:
    mode = choose_mode(pressure)
    pressure_score = pressure.pressure_score()
    oscillation_score = oscillation.normalized()
    replay_confidence = replay.confidence()
    has_starvation = not starvation.healthy()

    healthy = (
        pressure_score < 0.75
        and oscillation_score < 0.5
        and replay_confidence >= 0.99
        and not has_starvation
        and mode.mode is not OperatingMode.CORE_ONLY
    )

    return RuntimeHealth(
        pressure=pressure_score,
        oscillation=oscillation_score,
        replay_confidence=replay_confidence,
        starvation=has_starvation,
        mode=mode.mode.value,
        healthy=healthy,
        emitted_at=monotonic(),
    )
