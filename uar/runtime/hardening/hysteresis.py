"""Adaptive hysteresis helpers for UAR burn-in."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HysteresisBand:
    enter_at: float
    exit_at: float

    def __post_init__(self) -> None:
        if self.exit_at > self.enter_at:
            msg = "exit threshold must be less than or equal to enter threshold"
            raise ValueError(msg)

    def active_after(self, *, previous: bool, value: float) -> bool:
        if previous:
            return value > self.exit_at
        return value >= self.enter_at


@dataclass(frozen=True)
class HysteresisState:
    band: HysteresisBand
    active: bool = False

    def update(self, value: float) -> "HysteresisState":
        return HysteresisState(
            band=self.band,
            active=self.band.active_after(previous=self.active, value=value),
        )
