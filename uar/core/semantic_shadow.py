"""Runtime shadow observer for semantic replay validation.

The observer consumes an already-produced runtime event stream and adds only
semantic events.  It never calls skills, mutates runtime events, or changes the
Trust Spine.  Erasing its semantic events must recover the baseline stream
exactly.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from uar.core.semantic_trace import (
    SemanticTrace,
    project_nonsemantic_events,
    projected_event_hash,
    semantic_trace_from_events,
)

RuntimeEvent = Mapping[str, Any]

MAX_OBSERVER_P95_MICROSECONDS_PER_EVENT = 250.0
MAX_SHADOW_EVENT_EXPANSION = 6.0


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"


def _semantic_event(event_type: str, **payload: Any) -> RuntimeEvent:
    return {"type": event_type, "payload": payload}


def observe_runtime_semantics(
    events: Iterable[RuntimeEvent],
) -> tuple[RuntimeEvent, ...]:
    """Add a semantic shadow to a completed runtime event stream.

    Stage identity follows observed skill-start order. Concurrent starts share
    the same causal frontier, so harmless completion ordering is not invented
    as a dependency and later stages join all completed branches.
    """

    shadow = []
    pending: dict[str, deque[tuple[str, str, tuple[str, ...]]]] = defaultdict(
        deque
    )
    causal_frontier: set[str] = set()
    stage_index = 0

    for event in events:
        shadow.append(event)
        event_type = str(event.get("type", ""))
        skill_value = event.get("skill")
        skill = str(skill_value) if skill_value is not None else ""
        payload = event.get("payload")
        payload = payload if isinstance(payload, Mapping) else {}

        if event_type == "skill_start" and skill:
            stage_id = f"runtime:{stage_index:04d}:{skill}"
            candidate_id = skill
            stage_index += 1
            dependencies = tuple(sorted(causal_frontier))
            pending[skill].append((stage_id, candidate_id, dependencies))
            shadow.append(
                _semantic_event(
                    "semantic_stage",
                    stage_id=stage_id,
                    dependencies=list(dependencies),
                )
            )
            shadow.append(
                _semantic_event(
                    "candidate_generated",
                    stage_id=stage_id,
                    candidate_id=candidate_id,
                )
            )
            continue

        if event_type == "skill_retry" and skill and pending[skill]:
            stage_id, candidate_id, _ = pending[skill][0]
            attempt = int(payload.get("attempt", 0))
            shadow.append(
                _semantic_event(
                    "evidence_acquired",
                    stage_id=stage_id,
                    candidate_id=candidate_id,
                    evidence_id=_stable_id(
                        "runtime-retry",
                        {"stage_id": stage_id, "attempt": attempt},
                    ),
                )
            )
            continue

        if event_type in {"skill_complete", "skill_failed"} and skill:
            if not pending[skill]:
                # A cached parallel completion may not expose skill_start.
                stage_id = f"runtime:{stage_index:04d}:{skill}"
                candidate_id = skill
                stage_index += 1
                dependencies = tuple(sorted(causal_frontier))
                shadow.append(
                    _semantic_event(
                        "semantic_stage",
                        stage_id=stage_id,
                        dependencies=list(dependencies),
                    )
                )
                shadow.append(
                    _semantic_event(
                        "candidate_generated",
                        stage_id=stage_id,
                        candidate_id=candidate_id,
                    )
                )
            else:
                stage_id, candidate_id, dependencies = pending[skill].popleft()

            if event_type == "skill_complete":
                evidence_id = _stable_id("runtime-output", payload.get("result"))
                certificate_id = _stable_id(
                    "runtime-decision",
                    {"stage_id": stage_id, "evidence_id": evidence_id},
                )
                shadow.append(
                    _semantic_event(
                        "evidence_acquired",
                        stage_id=stage_id,
                        candidate_id=candidate_id,
                        evidence_id=evidence_id,
                    )
                )
                shadow.append(
                    _semantic_event(
                        "candidate_admitted",
                        stage_id=stage_id,
                        candidate_id=candidate_id,
                        certificate_id=certificate_id,
                        evidence_refs=[evidence_id],
                    )
                )
                shadow.append(
                    _semantic_event(
                        "candidate_committed",
                        stage_id=stage_id,
                        candidate_id=candidate_id,
                    )
                )
            else:
                shadow.append(
                    _semantic_event(
                        "candidate_rejected",
                        stage_id=stage_id,
                        candidate_id=candidate_id,
                        reason_code="runtime_skill_failed",
                    )
                )
            causal_frontier.difference_update(dependencies)
            causal_frontier.add(stage_id)
            continue

        if event_type == "complete":
            result_payload = {
                "status": payload.get("status"),
                "outputs": payload.get("outputs", []),
                "final_context": payload.get("final_context", {}),
            }
            shadow.append(
                _semantic_event(
                    "semantic_result",
                    result_id=_stable_id("runtime-result", result_payload),
                )
            )

    return tuple(shadow)


@dataclass(frozen=True, slots=True)
class RuntimeShadowPair:
    baseline_events: tuple[RuntimeEvent, ...]
    shadow_events: tuple[RuntimeEvent, ...]
    semantic_trace: SemanticTrace
    baseline_projection_hash: str
    shadow_projection_hash: str

    @property
    def projected_events_equal(self) -> bool:
        return (
            project_nonsemantic_events(self.shadow_events)
            == self.baseline_events
            and self.baseline_projection_hash == self.shadow_projection_hash
        )


@dataclass(frozen=True, slots=True)
class ShadowObserverOverhead:
    iterations: int
    baseline_events: int
    shadow_events: int
    mean_microseconds_per_event: float
    p95_microseconds_per_event: float
    event_expansion: float

    @property
    def within_envelope(self) -> bool:
        return (
            self.p95_microseconds_per_event
            <= MAX_OBSERVER_P95_MICROSECONDS_PER_EVENT
            and self.event_expansion <= MAX_SHADOW_EVENT_EXPANSION
        )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def measure_shadow_observer_overhead(
    events: Iterable[RuntimeEvent], *, iterations: int = 200
) -> ShadowObserverOverhead:
    """Measure observer-only cost against a declared validation envelope."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    baseline = tuple(events)
    if not baseline:
        raise ValueError("events must not be empty")

    samples = []
    shadow_event_count = 0
    for _ in range(iterations):
        started = time.perf_counter()
        shadow = observe_runtime_semantics(baseline)
        elapsed = time.perf_counter() - started
        shadow_event_count = len(shadow)
        samples.append((elapsed * 1_000_000) / len(baseline))

    return ShadowObserverOverhead(
        iterations=iterations,
        baseline_events=len(baseline),
        shadow_events=shadow_event_count,
        mean_microseconds_per_event=sum(samples) / len(samples),
        p95_microseconds_per_event=_p95(samples),
        event_expansion=shadow_event_count / len(baseline),
    )


def pair_runtime_with_shadow(
    execute: Callable[[], Iterable[RuntimeEvent]],
) -> RuntimeShadowPair:
    """Execute one runtime workload and attach a non-interfering shadow."""

    baseline = tuple(execute())
    shadow = observe_runtime_semantics(baseline)
    return RuntimeShadowPair(
        baseline_events=baseline,
        shadow_events=shadow,
        semantic_trace=semantic_trace_from_events(shadow),
        baseline_projection_hash=projected_event_hash(baseline),
        shadow_projection_hash=projected_event_hash(shadow),
    )


__all__ = [
    "MAX_OBSERVER_P95_MICROSECONDS_PER_EVENT",
    "MAX_SHADOW_EVENT_EXPANSION",
    "RuntimeShadowPair",
    "ShadowObserverOverhead",
    "measure_shadow_observer_overhead",
    "observe_runtime_semantics",
    "pair_runtime_with_shadow",
]
