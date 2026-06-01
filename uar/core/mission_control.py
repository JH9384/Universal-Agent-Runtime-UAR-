"""Mission Control — operator snapshot aggregating T1, T2, and T4.

Produces a single operator-facing snapshot combining replay confidence,
runtime health, certification, active run count, and recent warnings.

Trust Spine Phase: T5
Issues: #72, #55
Spec: docs/operations/MISSION_CONTROL.md
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from uar.core.certification import certify_runtime
from uar.core.replay_confidence import score_replay
from uar.core.runtime_health import (
    RuntimeHealthReport,
    build_runtime_snapshot,
    score_runtime_health,
)
from uar.memory.base_store import run_record_from_dict


@dataclass(slots=True)
class MissionControlSnapshot:
    """Aggregated operator view of the running UAR system."""

    replay_confidence: Optional[Dict[str, Any]]
    runtime_health: Optional[Dict[str, Any]]
    certification: Optional[Dict[str, Any]]
    active_runs: int
    recent_warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_snapshot(
    store: Any,
    registry: Any,
    burnin_report: Optional[Any] = None,
    snapshot: Optional[Any] = None,
) -> MissionControlSnapshot:
    """Build a Mission Control snapshot from live runtime state.

    Issue #85: pass a pre-built RuntimeSnapshot to avoid multiple store
    queries.  When snapshot is None one is built here from store.

    Args:
        store:          RunStore instance.
        registry:       SkillRegistry instance.
        burnin_report:  BurnInProxy from T3 runner, or None.
        snapshot:       Pre-built RuntimeSnapshot, or None (built here).

    Returns:
        MissionControlSnapshot with all Trust Spine evidence aggregated.
    """
    if snapshot is None:
        snapshot = build_runtime_snapshot(store)

    warnings: List[str] = []

    try:
        rh_report = score_runtime_health(
            registry=registry,
            burnin_report=burnin_report,
            snapshot=snapshot,
        )
        warnings.extend(rh_report.warnings)
    except Exception as exc:
        warnings.append(f"runtime_health: {exc}")
        rh_report = RuntimeHealthReport(
            score=0,
            tier="Critical",
            components={},
        )

    replay_confidence_dict = None
    replay_score = None
    try:
        if snapshot.latest_record is not None:
            run_record = run_record_from_dict(snapshot.latest_record)
            rc = score_replay(run_record)
            replay_score = rc.score
            replay_confidence_dict = rc.to_dict().get("confidence")
            warnings.extend(
                w.message for w in rc.warnings
                if w.severity in ("error", "warning")
            )
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Mission Control replay confidence scoring failed"
        )
        warnings.append(f"replay_confidence: {exc}")

    try:
        cert = certify_runtime(
            replay_confidence_score=replay_score,
            burnin_report=burnin_report,
            runtime_health_score=rh_report.score,
        )
        warnings.extend(cert.violations)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Mission Control certification scoring failed"
        )
        warnings.append(f"certification: {exc}")
        from uar.core.certification import CertificationReport
        cert = CertificationReport(
            score=0,
            level="Experimental",
            evidence={},
            violations=[str(exc)],
        )

    unique_warnings = list(dict.fromkeys(warnings))

    return MissionControlSnapshot(
        replay_confidence=replay_confidence_dict,
        runtime_health=rh_report.to_dict(),
        certification=cert.to_dict(),
        active_runs=snapshot.active_count,
        recent_warnings=unique_warnings[:20],
        timestamp=time.time(),
    )


__all__ = ["MissionControlSnapshot", "build_snapshot"]
