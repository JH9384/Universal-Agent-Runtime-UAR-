"""Mission Control API endpoint for the UAR Trust Spine.

Trust Spine Phase: T5
Issues: #72, #55
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.core.mission_control import build_snapshot
from uar.core.runtime_health import build_runtime_snapshot

security = HTTPBearer(auto_error=False)

router = APIRouter()

_ANALYTICS_CACHE = None


def _analytics_cache():
    global _ANALYTICS_CACHE
    if _ANALYTICS_CACHE is None:
        from uar.core.analytics_cache import ANALYTICS_CACHE
        _ANALYTICS_CACHE = ANALYTICS_CACHE
    return _ANALYTICS_CACHE


# In-memory ring buffer for MC snapshots (Issue #88).
# Stores up to the last 100 snapshots.  Resets on restart;
# no new storage layer.
_MC_HISTORY: List[dict] = []
_MC_HISTORY_MAX = 100


def _append_history(snapshot: dict) -> None:
    """Append a snapshot to the in-memory history buffer."""
    global _MC_HISTORY
    # Deduplicate: skip if last entry has same timestamp
    if (
        _MC_HISTORY
        and _MC_HISTORY[-1].get("timestamp") == snapshot.get("timestamp")
    ):
        return
    _MC_HISTORY.append(snapshot)
    if len(_MC_HISTORY) > _MC_HISTORY_MAX:
        _MC_HISTORY = _MC_HISTORY[-_MC_HISTORY_MAX:]


@router.get("/api/uar/mission-control")
async def get_mission_control(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return a Mission Control snapshot aggregating T1, T2, and T4."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    from uar.api.server import store
    from uar.core.registry import registry
    from uar.api.routers.burn_in import BurnInProxy

    rt_snapshot = build_runtime_snapshot(store)
    mc_snapshot = build_snapshot(
        store=store,
        registry=registry,
        burnin_report=BurnInProxy.from_latest(store=store),
        snapshot=rt_snapshot,
    )
    snapshot_dict = mc_snapshot.to_dict()
    _append_history(snapshot_dict)
    return snapshot_dict


@router.get("/api/uar/mission-control/history")
async def get_mission_control_history(
    hours: int = Query(24, ge=1, le=168),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return historical Mission Control snapshots for trend analysis.

    Issue #88 — Phase D1: Historical Trends.  Returns the last N hours
    of stored snapshots (up to _MC_HISTORY_MAX entries).  History is
    in-memory and resets on server restart.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time
    cutoff = time.time() - (hours * 3600)
    filtered = [s for s in _MC_HISTORY if s.get("timestamp", 0) >= cutoff]
    return {
        "hours": hours,
        "count": len(filtered),
        "snapshots": filtered,
    }


@router.get("/api/uar/confidence-drift")
async def get_confidence_drift(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(1000, ge=1, le=50000),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Diagnose confidence drift and its root contributors.

    Issue #94 — Phase D2.2: Confidence Drift.
    Correlates confidence score changes with failure clusters and
    burn-in evidence to produce actionable operator diagnosis.
    Zero new storage layer.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time
    from uar.api.server import store
    from uar.api.routers.burn_in import _BURNIN_HISTORY

    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    cached = _analytics_cache().get(
        "confidence-drift", user, is_admin, hours, limit
    )
    if cached is not None:
        return cached

    cutoff = time.time() - (hours * 3600)

    # Build snapshot from recent runs
    all_runs = store.list_records(
        user_id=user if is_admin else user, limit=limit
    )
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    from uar.core.analytics_snapshot import (
        build_analytics_snapshot,
        extract_confidence_drift,
    )

    snapshot = build_analytics_snapshot(
        recent_runs, user, is_admin, hours, limit
    )
    result = extract_confidence_drift(
        snapshot, _MC_HISTORY, _BURNIN_HISTORY, hours
    )
    result["meta"] = {
        "runs_loaded": len(all_runs),
        "runs_analyzed": snapshot.runs_analyzed,
        "limit": limit,
        "truncated": len(all_runs) >= limit,
    }
    _analytics_cache().set(
        "confidence-drift", user, is_admin, hours, limit, result
    )
    return result


@router.get("/api/uar/alerts/summary")
async def get_alerts_summary(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(1000, ge=1, le=50000),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return a prioritized alert summary for the operator banner.

    D4A-3 — Alert Banner.
    Derives the single most important alert from Mission Control,
    Confidence Drift, Failure Hotspots, and Recipe Intelligence.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time
    from uar.api.server import store
    from uar.core.registry import registry
    from uar.api.routers.burn_in import BurnInProxy, _BURNIN_HISTORY
    from uar.core.mission_control import build_snapshot
    from uar.core.runtime_health import build_runtime_snapshot
    from uar.core.analytics_snapshot import (
        build_analytics_snapshot,
        extract_confidence_drift,
        extract_failure_hotspots,
        extract_recipe_intelligence,
    )

    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    cached = _analytics_cache().get(
        "alerts-summary", user, is_admin, hours, limit
    )
    if cached is not None:
        return cached

    cutoff = time.time() - (hours * 3600)

    # ---- Mission Control snapshot ----
    rt_snapshot = build_runtime_snapshot(store)
    mc_snapshot = build_snapshot(
        store=store,
        registry=registry,
        burnin_report=BurnInProxy.from_latest(store=store),
        snapshot=rt_snapshot,
    )
    mc = mc_snapshot.to_dict()
    cert = mc.get("certification") or {}
    cert_level = str(cert.get("level", "")).lower()
    cert_score = cert.get("score")
    recent_warnings = mc.get("recent_warnings", [])
    burnin_passed = cert.get("evidence", {}).get("burnin_passed")

    # ---- Analytics snapshot ----
    all_runs = store.list_records(
        user_id=user if is_admin else user, limit=limit
    )
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]
    snap = build_analytics_snapshot(
        recent_runs, user, is_admin, hours, limit
    )

    # Confidence drift
    cd = extract_confidence_drift(
        snap, _MC_HISTORY, _BURNIN_HISTORY, hours
    )

    # Failure hotspots
    hs = extract_failure_hotspots(snap, top=10)

    # Recipe intelligence
    ri = extract_recipe_intelligence(snap)

    alerts: list[dict] = []

    # ---- Critical alerts ----
    if "degraded" in cert_level or "failed" in cert_level:
        alerts.append({
            "level": "critical",
            "source": "certification",
            "message": f"Certification degraded: {cert_level}",
            "detail": cert.get("violations", []),
        })
    if cert_score is not None and cert_score < 50:
        alerts.append({
            "level": "critical",
            "source": "certification",
            "message": f"Certification score collapsed to {cert_score}",
        })
    if cd.get("state") == "degrading" and cd.get("delta", 0) < -10:
        alerts.append({
            "level": "critical",
            "source": "confidence",
            "message": (
                f"Confidence collapsing: {cd.get('current_score')}"
                f" (Δ {cd.get('delta')})"
            ),
        })
    for node in hs.get("nodes", []):
        if node.get("severity") == "critical":
            alerts.append({
                "level": "critical",
                "source": "hotspot",
                "message": (
                    f"Critical hotspot: {node['skill']}"
                    f" ({node['failure_rate'] * 100:.0f}% failure)"
                ),
            })

    # ---- Warning alerts ----
    if cd.get("state") == "degrading":
        alerts.append({
            "level": "warning",
            "source": "confidence",
            "message": (
                f"Confidence degrading: {cd.get('current_score')}"
                f" (Δ {cd.get('delta')})"
            ),
        })
    if burnin_passed is False:
        alerts.append({
            "level": "warning",
            "source": "burnin",
            "message": "Burn-In not passed",
        })
    for node in hs.get("nodes", []):
        if node.get("severity") == "warning":
            alerts.append({
                "level": "warning",
                "source": "hotspot",
                "message": (
                    f"Warning hotspot: {node['skill']}"
                    f" ({node['failure_rate'] * 100:.0f}% failure)"
                ),
            })
    if recent_warnings:
        alerts.append({
            "level": "warning",
            "source": "mission_control",
            "message": recent_warnings[0],
        })

    # ---- Informational alerts ----
    if cd.get("state") == "improving":
        alerts.append({
            "level": "info",
            "source": "confidence",
            "message": (
                f"Confidence improving: {cd.get('current_score')}"
                f" (Δ +{cd.get('delta')})"
            ),
        })
    recommended = [r for r in ri.get("recipes", [])
                   if r.get("classification") == "recommended"]
    if recommended:
        alerts.append({
            "level": "info",
            "source": "recipe",
            "message": (
                f"New recommended recipe: {recommended[0]['recipe']}"
            ),
        })
    if burnin_passed is True:
        alerts.append({
            "level": "info",
            "source": "burnin",
            "message": "Burn-In passed",
        })

    # No alerts → healthy state
    if not alerts:
        alerts.append({
            "level": "info",
            "source": "system",
            "message": "All systems nominal",
        })

    priority = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: priority.get(a["level"], 2))

    result = {
        "hours": hours,
        "count": len(alerts),
        "top_alert": alerts[0],
        "alerts": alerts[:5],
    }
    _analytics_cache().set(
        "alerts-summary", user, is_admin, hours, limit, result
    )
    return result
