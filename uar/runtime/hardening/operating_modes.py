"""Operating modes for UAR hardening."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .pressure_metrics import PressureSnapshot


class OperatingMode(str, Enum):
    NORMAL = "normal"
    OBSERVER_SAMPLED = "observer_sampled"
    OBSERVER_REDUCED = "observer_reduced"
    TRACE_COMPACT = "trace_compact"
    CORE_ONLY = "core_only"


@dataclass(frozen=True)
class ModeDecision:
    mode: OperatingMode
    replay_identity_required: bool
    event_validity_required: bool
    observer_ratio: float
    reason: str


def choose_mode(snapshot: PressureSnapshot) -> ModeDecision:
    score = snapshot.pressure_score()

    if score < 0.35:
        return ModeDecision(
            OperatingMode.NORMAL,
            True,
            True,
            1.0,
            "normal envelope",
        )
    if score < 0.55:
        return ModeDecision(
            OperatingMode.OBSERVER_SAMPLED,
            True,
            True,
            0.5,
            "observer cadence reduced",
        )
    if score < 0.75:
        return ModeDecision(
            OperatingMode.OBSERVER_REDUCED,
            True,
            True,
            0.2,
            "observer work reduced",
        )
    if score < 0.9:
        return ModeDecision(
            OperatingMode.TRACE_COMPACT,
            True,
            True,
            0.1,
            "trace detail compacted",
        )
    return ModeDecision(
        OperatingMode.CORE_ONLY,
        True,
        True,
        0.0,
        "core runtime protected",
    )
