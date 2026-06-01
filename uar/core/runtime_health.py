"""Runtime Health scoring for UAR.

RuntimeHealth measures whether the runtime is operating within safe and
predictable execution boundaries. Scores are derived on demand from
existing store, registry, and circuit-breaker state — no daemon, no
accumulator.

Issue #85: A single RuntimeSnapshot query replaces multiple independent
store.list_records() calls so that Mission Control, Certification, and
Runtime Health all share one store read per request.

Trust Spine Phase: T2
Issue: #83, #85
Spec: docs/operations/RUNTIME_HEALTH.md
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ComponentHealth:
    """Health score and status for a single runtime component."""

    score: int
    status: str
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeHealthReport:
    """Composite runtime health report.

    score is 0-100 (weighted composite of component scores).
    tier is one of: Nominal | Healthy | Degraded | Unstable | Critical
    components maps component name -> ComponentHealth.
    """

    score: int
    tier: str
    components: Dict[str, ComponentHealth]
    warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable report."""
        return {
            "score": self.score,
            "tier": self.tier,
            "components": {
                name: asdict(c)
                for name, c in self.components.items()
            },
            "warnings": list(self.warnings),
            "timestamp": self.timestamp,
        }


@dataclass(slots=True)
class RuntimeSnapshot:
    """Single-pass store read shared across all Trust Spine scorers.

    Build once via build_runtime_snapshot() and pass to
    score_runtime_health() and build_snapshot() so that a single
    Mission Control request issues exactly one store query.

    Attributes:
        recent_records: Most recent N run records (N=500 by default).
        latest_record:  The single most recent record, or None.
        active_count:   Count of records with status running/pending/queued.
        queried_at:     Unix timestamp when the snapshot was taken.
    """

    recent_records: List[dict]
    latest_record: Optional[dict]
    active_count: int
    store_error: Optional[str] = None
    queried_at: float = field(default_factory=time.time)


def build_runtime_snapshot(
    store: Any,
    limit: int = 500,
) -> RuntimeSnapshot:
    """Query the store once and return a RuntimeSnapshot.

    All downstream scorers (runtime_health, mission_control,
    certification) accept this snapshot instead of querying the store
    independently.

    Args:
        store: RunStore instance.
        limit: Maximum number of recent records to load (default 500).

    Returns:
        RuntimeSnapshot populated from a single store.list_records() call.
    """
    import copy

    store_error = None
    try:
        raw_records = list(store.list_records(limit=limit) or [])
    except Exception as exc:
        store_error = str(exc)
        raw_records = []

    # Defensive deep copy so downstream scorers cannot accidentally
    # mutate the snapshot (e.g. deleting keys, modifying nested dicts).
    records = [copy.deepcopy(r) for r in raw_records]

    latest = records[0] if records else None
    active_count = sum(
        1 for r in records
        if r.get("status") in ("running", "pending", "queued")
    )
    return RuntimeSnapshot(
        recent_records=records,
        latest_record=latest,
        active_count=active_count,
        store_error=store_error,
    )


def health_tier(score: int) -> str:
    """Map composite health score to operator-facing tier."""
    if score >= 95:
        return "Nominal"
    if score >= 75:
        return "Healthy"
    if score >= 50:
        return "Degraded"
    if score >= 25:
        return "Unstable"
    return "Critical"


def _score_execution(
    records: List[dict],
    warnings: List[str],
) -> ComponentHealth:
    """Score execution health from pre-loaded run records."""
    sample = records[:50]

    if not sample:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=["No recent runs — baseline healthy"],
        )

    total = len(sample)
    failed = sum(
        1 for r in sample
        if r.get("status") in ("failed", "error", "timeout")
    )
    failure_rate = failed / total if total > 0 else 0.0

    if failure_rate == 0:
        score = 100
        status = "nominal"
    elif failure_rate <= 0.05:
        score = 90
        status = "healthy"
    elif failure_rate <= 0.20:
        score = 70
        status = "degraded"
        warnings.append(
            f"execution: {failed}/{total} recent runs failed"
        )
    elif failure_rate <= 0.50:
        score = 40
        status = "unstable"
        warnings.append(
            f"execution: high failure rate {failed}/{total}"
        )
    else:
        score = 10
        status = "critical"
        warnings.append(
            f"execution: critical failure rate {failed}/{total}"
        )

    return ComponentHealth(
        score=score,
        status=status,
        notes=[f"recent_runs={total}", f"failed={failed}"],
    )


def _score_skills(
    registry: Any,
    circuit_states: Dict[str, str],
    warnings: List[str],
) -> ComponentHealth:
    """Score skill health from registry + circuit breaker states."""
    try:
        if not hasattr(registry, "list") or not callable(registry.list):
            raise AttributeError(
                f"registry {type(registry).__name__} has no list() method"
            )
        skills = list(registry.list() or [])
    except Exception as exc:
        warnings.append(f"skills: registry.list() failed: {exc}")
        return ComponentHealth(
            score=0, status="error", notes=[str(exc)]
        )

    if not skills:
        warnings.append("skills: no skills registered")
        return ComponentHealth(
            score=50,
            status="degraded",
            notes=["No skills registered"],
        )

    open_breakers = [
        name for name, state in circuit_states.items()
        if state == "open"
    ]
    if not open_breakers:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=[f"skills={len(skills)}", "no_open_breakers"],
        )

    ratio_open = len(open_breakers) / max(len(skills), 1)
    if ratio_open <= 0.10:
        score = 80
        status = "healthy"
    elif ratio_open <= 0.30:
        score = 55
        status = "degraded"
        warnings.append(
            f"skills: {len(open_breakers)} circuit(s) open"
        )
    else:
        score = 20
        status = "critical"
        warnings.append(
            f"skills: {len(open_breakers)} circuits open "
            f"({ratio_open:.0%} of skills)"
        )
    return ComponentHealth(
        score=score,
        status=status,
        notes=[
            f"skills={len(skills)}",
            f"open_breakers={open_breakers}",
        ],
    )


def _score_events(
    records: List[dict],
    warnings: List[str],
) -> ComponentHealth:
    """Score event health from pre-loaded run records."""
    sample = records[:20]

    if not sample:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=["No recent runs to score"],
        )

    with_events = sum(1 for r in sample if r.get("events") is not None)
    ratio = with_events / len(sample)
    if ratio >= 0.95:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=[f"event_coverage={ratio:.0%}"],
        )
    if ratio >= 0.75:
        score, status = 75, "healthy"
    elif ratio >= 0.50:
        score, status = 50, "degraded"
        warnings.append(
            f"events: only {ratio:.0%} of recent runs have events"
        )
    else:
        score, status = 20, "critical"
        warnings.append(
            f"events: low event coverage {ratio:.0%}"
        )
    return ComponentHealth(
        score=score,
        status=status,
        notes=[
            f"runs_checked={len(sample)}",
            f"with_events={with_events}",
        ],
    )


def _score_streaming(
    circuit_states: Dict[str, str],
    warnings: List[str],
) -> ComponentHealth:
    """Score streaming health from circuit breaker states."""
    streaming_keys = [
        k for k in circuit_states
        if any(
            kw in k.lower()
            for kw in ("stream", "websocket", "ws", "push")
        )
    ]
    if not streaming_keys:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=["No streaming circuit breakers registered"],
        )
    open_streaming = [
        k for k in streaming_keys
        if circuit_states[k] == "open"
    ]
    if not open_streaming:
        return ComponentHealth(
            score=100,
            status="nominal",
            notes=[f"streaming_circuits={len(streaming_keys)}"],
        )
    warnings.append(
        f"streaming: {len(open_streaming)} circuit(s) open"
    )
    score = max(0, 100 - len(open_streaming) * 25)
    return ComponentHealth(
        score=score,
        status="degraded" if score >= 50 else "critical",
        notes=[f"open={open_streaming}"],
    )


def _score_pressure(
    burnin_report: Optional[Any],
    warnings: List[str],
) -> ComponentHealth:
    """Score pressure health from burn-in evidence."""
    if burnin_report is None:
        return ComponentHealth(
            score=75,
            status="unknown",
            notes=["No burn-in report available; assuming moderate health"],
        )
    try:
        score = int(burnin_report.score)
        passed = bool(burnin_report.passed)
        status = "nominal" if passed else "degraded"
        if not passed:
            warnings.append(
                f"pressure: burn-in did not pass (score={score})"
            )
        return ComponentHealth(
            score=score,
            status=status,
            notes=[
                f"burnin_score={score}",
                f"burnin_passed={passed}",
            ],
        )
    except Exception as exc:
        warnings.append(f"pressure: burn-in report parse error: {exc}")
        return ComponentHealth(
            score=50, status="unknown", notes=[str(exc)]
        )


def score_runtime_health(
    registry: Any,
    burnin_report: Optional[Any] = None,
    snapshot: Optional[RuntimeSnapshot] = None,
    store: Optional[Any] = None,
) -> RuntimeHealthReport:
    """Score runtime health from a RuntimeSnapshot, registry, and burn-in.

    Preferred call (Issue #85 — one store scan per request):

        snap = build_runtime_snapshot(store)
        report = score_runtime_health(registry, burnin_report, snapshot=snap)

    Legacy call (backward-compatible, issues its own store queries):

        report = score_runtime_health(registry, burnin_report, store=store)

    Args:
        registry:       SkillRegistry instance.
        burnin_report:  BurnInProxy from T3, or None.
        snapshot:       Pre-built RuntimeSnapshot (preferred).
        store:          RunStore instance (used only when snapshot is None).

    Returns:
        RuntimeHealthReport with score, tier, and per-component breakdown.
    """
    if snapshot is None:
        if store is None:
            raise ValueError(
                "score_runtime_health requires either snapshot= or store="
            )
        snapshot = build_runtime_snapshot(store)

    warnings: List[str] = []

    if snapshot.store_error is not None:
        warnings.append(f"store unreachable: {snapshot.store_error}")

    try:
        circuit_states = _get_circuit_states()
    except Exception as exc:
        warnings.append(f"circuit breakers unavailable: {exc}")
        circuit_states = {}

    components = {
        "execution": _score_execution(
            snapshot.recent_records, warnings
        ),
        "skills": _score_skills(registry, circuit_states, warnings),
        "events": _score_events(snapshot.recent_records, warnings),
        "streaming": _score_streaming(circuit_states, warnings),
        "pressure": _score_pressure(burnin_report, warnings),
    }

    weighted = (
        components["execution"].score * 0.25
        + components["skills"].score * 0.20
        + components["events"].score * 0.20
        + components["streaming"].score * 0.15
        + components["pressure"].score * 0.20
    )
    score = int(round(max(0.0, min(100.0, weighted))))

    if snapshot.store_error is not None:
        score = min(score, 50)
        warnings.append(
            "runtime health degraded due to store failure"
        )

    return RuntimeHealthReport(
        score=score,
        tier=health_tier(score),
        components=components,
        warnings=warnings,
        timestamp=time.time(),
    )


def _get_circuit_states() -> Dict[str, str]:
    try:
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker_states,
        )
        return dict(get_circuit_breaker_states())
    except ImportError:
        return {}


__all__ = [
    "ComponentHealth",
    "RuntimeHealthReport",
    "RuntimeSnapshot",
    "build_runtime_snapshot",
    "health_tier",
    "score_runtime_health",
]
