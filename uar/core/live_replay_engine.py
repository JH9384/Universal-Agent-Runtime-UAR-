"""Live replay engine.

Provides event capture, replay fingerprinting, and divergence localization
for certified runtime replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .event_hashing import replay_fingerprint
from .replay_drift_comparator import ReplayDriftComparator, ReplayDriftResult


@dataclass(slots=True)
class ReplayTrace:
    replay_id: str
    events: List[Dict[str, Any]] = field(default_factory=list)

    def append(self, event: Dict[str, Any]) -> None:
        self.events.append(dict(event))

    @property
    def fingerprint(self) -> str:
        return replay_fingerprint(self.events)


@dataclass(slots=True)
class ReplayVerificationResult:
    accepted: bool
    baseline_fingerprint: str
    candidate_fingerprint: str
    drift: ReplayDriftResult
    divergence_index: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "baseline_fingerprint": self.baseline_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "drift": {
                "topology_drift": self.drift.topology_drift,
                "semantic_drift": self.drift.semantic_drift,
                "governance_drift": self.drift.governance_drift,
                "total_drift": self.drift.total_drift,
            },
            "divergence_index": self.divergence_index,
        }


class LiveReplayEngine:
    """Captures and verifies runtime replay traces."""

    def __init__(self) -> None:
        self.comparator = ReplayDriftComparator()

    def create_trace(self, replay_id: str) -> ReplayTrace:
        return ReplayTrace(replay_id=replay_id)

    def first_divergence(
        self,
        baseline: ReplayTrace,
        candidate: ReplayTrace,
    ) -> int | None:
        limit = min(len(baseline.events), len(candidate.events))
        for index in range(limit):
            if baseline.events[index] != candidate.events[index]:
                return index
        if len(baseline.events) != len(candidate.events):
            return limit
        return None

    def verify(
        self,
        baseline: ReplayTrace,
        candidate: ReplayTrace,
    ) -> ReplayVerificationResult:
        baseline_fingerprint = baseline.fingerprint
        candidate_fingerprint = candidate.fingerprint
        accepted = baseline_fingerprint == candidate_fingerprint
        divergence_index = self.first_divergence(baseline, candidate)

        drift = self.comparator.compare(
            topology_a=baseline_fingerprint,
            topology_b=candidate_fingerprint,
            semantic_a=baseline_fingerprint,
            semantic_b=candidate_fingerprint,
            governance_a=baseline.replay_id,
            governance_b=candidate.replay_id,
        )

        return ReplayVerificationResult(
            accepted=accepted,
            baseline_fingerprint=baseline_fingerprint,
            candidate_fingerprint=candidate_fingerprint,
            drift=drift,
            divergence_index=divergence_index,
        )
