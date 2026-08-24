"""Mission Control — operator snapshot aggregating T1, T2, and T4."""

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
from uar.config import _uar_start_time
from uar.memory.base_store import run_record_from_dict
from uar.version import get_uar_version


@dataclass(slots=True)
class MissionControlSnapshot:
    replay_confidence: Optional[Dict[str, Any]]
    runtime_health: Optional[Dict[str, Any]]
    certification: Optional[Dict[str, Any]]
    active_runs: int
    recent_warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    trust_summary: Optional[Dict[str, Any]] = None
    fleet_summary: Optional[Dict[str, Any]] = None
    incident_summary: Optional[Dict[str, Any]] = None
    server_version: str = "unknown"
    uptime_seconds: int = 0
    skills_available: int = 0
    skills_total: int = 0
    circuit_breakers: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_snapshot(
    store: Any,
    registry: Any,
    burnin_report: Optional[Any] = None,
    snapshot: Optional[Any] = None,
) -> MissionControlSnapshot:
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
            score=0, tier="Critical", components={}
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
                w.message
                for w in rc.warnings
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

    outcomes = []
    metadata = []
    trust_summary = None
    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=50000)
        metadata = store.get_recommendation_metadata(limit=50000)
        trust_result = compute_trust(outcomes, metadata)
        types = trust_result.get("recommendation_types", [])
        trust_summary = {
            "system_calibration_error": trust_result.get(
                "system_calibration_error"
            ),
            "recommendation_type_count": len(types),
            "top_trusted": types[0]["type"] if types else None,
            "top_trust_score": types[0]["trust_score"] if types else None,
            "drift_count": sum(
                1 for t in types if t.get("drift_penalty", 0.0) > 0.0
            ),
            "highly_trusted_count": sum(
                1 for t in types if t.get("trust_score", 0.0) >= 0.80
            ),
        }
    except Exception as exc:
        import logging as _logging

        _logging.getLogger(__name__).exception("Trust summary failed")
        warnings.append(f"trust_summary: {exc}")

    records = list(getattr(snapshot, "recent_records", []) or [])

    fleet_summary = None
    try:
        from uar.core.fleet_linkage import attach_linkage_to_fleet_summary
        from uar.core.fleet_signals import (
            build_fleet_signals,
            build_fleet_summary,
        )

        fleet_summary = attach_linkage_to_fleet_summary(
            build_fleet_summary(build_fleet_signals(records))
        )
    except Exception as exc:
        import logging as _logging

        _logging.getLogger(__name__).exception("Fleet summary failed")
        warnings.append(f"fleet_summary: {exc}")

    incident_summary = None
    try:
        from uar.core.incident_intelligence import (
            build_incident_intelligence_summary,
        )

        incident_summary = build_incident_intelligence_summary(
            records,
            outcomes=outcomes,
            recommendation_metadata=metadata,
        )
    except Exception as exc:
        import logging as _logging

        _logging.getLogger(__name__).exception("Incident summary failed")
        warnings.append(f"incident_summary: {exc}")

    skills_available = 0
    skills_total = 0
    circuit_breakers = []
    try:
        if hasattr(registry, "list") and callable(registry.list):
            skills_total = len(list(registry.list() or []))
            for name in registry.list() or []:
                try:
                    registry.get(name)
                    skills_available += 1
                except Exception as _exc:
                    import logging as _logging

                    _logging.getLogger(__name__).debug(
                        "Skill %s listed but not gettable: %s", name, _exc
                    )
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker_details,
        )
        from uar.core.async_utils import run_sync_safe

        cb_details = run_sync_safe(get_circuit_breaker_details())
        circuit_breakers = [
            {"name": name, **info} for name, info in cb_details.items()
        ]
    except Exception as exc:
        warnings.append(f"registry_health: {exc}")

    unique_warnings = list(dict.fromkeys(warnings))

    return MissionControlSnapshot(
        replay_confidence=replay_confidence_dict,
        runtime_health=rh_report.to_dict(),
        certification=cert.to_dict(),
        active_runs=snapshot.active_count,
        recent_warnings=unique_warnings[:20],
        timestamp=time.time(),
        trust_summary=trust_summary,
        fleet_summary=fleet_summary,
        incident_summary=incident_summary,
        server_version=get_uar_version(),
        uptime_seconds=int(time.time() - _uar_start_time),
        skills_available=skills_available,
        skills_total=skills_total,
        circuit_breakers=circuit_breakers,
    )


__all__ = ["MissionControlSnapshot", "build_snapshot"]
