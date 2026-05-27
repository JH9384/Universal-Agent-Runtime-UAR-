"""Replay reconstruction helpers for burn-in certification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayFragment:
    sequence: int
    valid: bool = True


@dataclass(frozen=True)
class ReconstructionResult:
    recovered_sequences: tuple[int, ...]
    missing_sequences: tuple[int, ...]

    def complete(self) -> bool:
        return not self.missing_sequences


def reconstruct(fragments: tuple[ReplayFragment, ...]) -> ReconstructionResult:
    ordered = sorted(fragment.sequence for fragment in fragments if fragment.valid)

    if not ordered:
        return ReconstructionResult((), ())

    expected = set(range(min(ordered), max(ordered) + 1))
    actual = set(ordered)

    return ReconstructionResult(
        recovered_sequences=tuple(sorted(actual)),
        missing_sequences=tuple(sorted(expected - actual)),
    )
