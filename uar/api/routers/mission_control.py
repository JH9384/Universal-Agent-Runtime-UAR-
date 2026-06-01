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


@router.get("/api/uar/recommendations")
async def get_recommendations(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(1000, ge=1, le=50000),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return operational recommendations derived from accumulated history.

    Omega-5.1: Surface the Learning Layer.

    Derives recommendations from:
    - Recurring failure patterns (Multi-Run Intelligence)
    - Recovery atlas (historical recovery paths)
    - Topology evolution (growth and complexity signals)
    - Governance trends (approval / tampered / certification rates)

    Uses the same AnalyticsCache lifecycle as all other analytics
    endpoints: invalidated on new runs and burn-in execution.
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

    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    cached = _analytics_cache().get(
        "recommendations", user, is_admin, hours, limit
    )
    if cached is not None:
        return cached

    cutoff = time.time() - (hours * 3600)

    # Build analytics snapshot from recent runs
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
    )
    from uar.core.multi_run_intelligence import (
        find_recurring_failures,
        build_recovery_atlas,
    )
    from uar.core.operational_learning import (
        generate_all_recommendations,
    )

    snap = build_analytics_snapshot(
        recent_runs, user, is_admin, hours, limit
    )

    # Extract multi-run intelligence
    recurring = find_recurring_failures(recent_runs, min_occurrences=2)
    recovery = build_recovery_atlas(recent_runs)

    # Topology evolution: compare earliest and latest snapshot
    # For a single-window request we use one point; for future
    # multi-window aggregation the API can accept snapshot history.
    topology_points = []
    if snap.topology_nodes:
        topology_points = [
            {
                "timestamp": time.time(),
                "total_nodes": len(snap.topology_nodes),
                "total_edges": len(snap.topology_edges),
                "hot_region": (
                    max(
                        snap.topology_nodes.items(),
                        key=lambda x: x[1].invocations,
                    )[0]
                    if snap.topology_nodes
                    else None
                ),
            }
        ]

    # Governance summaries: derive from analytics snapshot
    total_runs = snap.runs_analyzed
    failure_rate = (
        snap.total_failures / total_runs if total_runs else 0.0
    )
    cert_rate = (
        (total_runs - snap.total_failures) / total_runs
        if total_runs
        else 1.0
    )
    gov_summaries = [
        {
            "approval_rate": 1.0 - failure_rate,
            "tampered": 0,
            "total_records": total_runs,
            "certification_rate": cert_rate,
        }
    ]

    recommendations = generate_all_recommendations(
        recurring_patterns=recurring,
        recovery_paths=recovery,
        topology_points=topology_points,
        governance_summaries=gov_summaries,
    )

    # Ω-5.4: Apply adaptive confidence modifiers based on operator feedback
    try:
        shown = store.get_shown_recommendations(user_id=user, limit=50000)
        feedback = store.get_feedback(user_id=user, limit=50000)
        from uar.core.adaptive_confidence import (
            build_quality_stats,
            compute_modifier,
        )
        quality = build_quality_stats(shown, feedback)
        for rec in recommendations:
            stats = quality.get(rec.recommendation_id, {})
            modifier = compute_modifier(
                stats.get("shown_count", 0),
                stats.get("accepted_count", 0),
                stats.get("rejected_count", 0),
                stats.get("dismissed_count", 0),
            )
            rec.adaptive_modifier = modifier
            rec.base_confidence = rec.confidence
            rec.confidence = rec.base_confidence * modifier
    except Exception:
        pass  # adaptive confidence is best-effort

    result = {
        "generated_at": time.time(),
        "hours": hours,
        "runs_analyzed": total_runs,
        "recommendations": [r.to_dict() for r in recommendations],
        "sources": {
            "recurring_patterns": len(recurring),
            "recovery_paths": len(recovery),
            "topology_points": len(topology_points),
            "governance_periods": len(gov_summaries),
        },
    }
    _analytics_cache().set(
        "recommendations", user, is_admin, hours, limit, result
    )
    # Ω-5.3: Track that each recommendation was shown to the operator
    # Ω-6a: Also capture metadata for effectiveness ranking
    for rec in recommendations:
        try:
            store.record_recommendation_shown(
                rec.recommendation_id, user_id=user
            )
            store.record_recommendation_metadata(
                rec.recommendation_id,
                category=rec.category,
                source=rec.source,
                title=rec.title,
                confidence=rec.confidence,
            )
        except Exception:
            pass  # shown and metadata tracking is best-effort
    return result


@router.get("/api/uar/recommendations/quality")
async def get_recommendation_quality(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Recommendation quality metrics.

    Omega-5.3: Measures recommendation effectiveness from operator
    feedback. Returns per-recommendation-id stats plus aggregates.
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

    user = user_info.get("user") if user_info else None

    import time
    from uar.api.server import store

    shown = store.get_shown_recommendations(user_id=user, limit=50000)
    feedback = store.get_feedback(user_id=user, limit=50000)
    outcomes = store.get_outcomes(limit=50000)

    from collections import defaultdict

    stats: dict[str, dict] = defaultdict(
        lambda: {
            "shown_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "dismissed_count": 0,
            "resolved_count": 0,
            "recurred_count": 0,
            "accept_times": [],
            "reject_times": [],
        }
    )

    for s in shown:
        rid = s.get("recommendation_id")
        if rid:
            stats[rid]["shown_count"] += 1

    for f in feedback:
        rid = f.get("recommendation_id")
        action = f.get("action")
        if not rid or not action:
            continue
        if action == "accept":
            stats[rid]["accepted_count"] += 1
            stats[rid]["accept_times"].append(f.get("created_at", 0))
        elif action == "reject":
            stats[rid]["rejected_count"] += 1
            stats[rid]["reject_times"].append(f.get("created_at", 0))
        elif action == "dismiss":
            stats[rid]["dismissed_count"] += 1

    for o in outcomes:
        rid = o.get("recommendation_id")
        out_type = o.get("outcome_type")
        if not rid or not out_type:
            continue
        if out_type == "resolved":
            stats[rid]["resolved_count"] += 1
        elif out_type == "recurred":
            stats[rid]["recurred_count"] += 1

    metrics: list[dict] = []
    for rid, s in stats.items():
        shown_count = s["shown_count"]
        accepted = s["accepted_count"]
        rejected = s["rejected_count"]
        dismissed = s["dismissed_count"]
        resolved = s["resolved_count"]
        recurred = s["recurred_count"]
        total_outcomes = resolved + recurred
        metrics.append(
            {
                "recommendation_id": rid,
                "shown_count": shown_count,
                "accepted_count": accepted,
                "rejected_count": rejected,
                "dismissed_count": dismissed,
                "resolved_count": resolved,
                "recurred_count": recurred,
                "acceptance_rate": round(accepted / shown_count, 2)
                if shown_count
                else 0.0,
                "rejection_rate": round(rejected / shown_count, 2)
                if shown_count
                else 0.0,
                "dismissal_rate": round(dismissed / shown_count, 2)
                if shown_count
                else 0.0,
                "resolution_rate": round(resolved / total_outcomes, 2)
                if total_outcomes
                else 0.0,
            }
        )

    total_shown = sum(s["shown_count"] for s in stats.values())
    total_accept = sum(s["accepted_count"] for s in stats.values())
    total_reject = sum(s["rejected_count"] for s in stats.values())
    total_dismiss = sum(s["dismissed_count"] for s in stats.values())
    total_resolved = sum(s["resolved_count"] for s in stats.values())
    total_recurred = sum(s["recurred_count"] for s in stats.values())
    total_outcomes_all = total_resolved + total_recurred

    return {
        "generated_at": time.time(),
        "recommendation_count": len(metrics),
        "total_shown": total_shown,
        "total_accepted": total_accept,
        "total_rejected": total_reject,
        "total_dismissed": total_dismiss,
        "overall_acceptance_rate": round(total_accept / total_shown, 2)
        if total_shown
        else 0.0,
        "total_resolved": total_resolved,
        "total_recurred": total_recurred,
        "overall_resolution_rate": round(
            total_resolved / total_outcomes_all, 2
        )
        if total_outcomes_all
        else 0.0,
        "metrics": metrics,
    }


@router.get("/api/uar/recommendations/effectiveness")
async def get_recommendation_effectiveness(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Recommendation effectiveness rankings.

    Omega-6a: Operational leaderboard showing which recommendation
    types historically resolve issues, with decay weighting and
    drift detection.
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

    from uar.api.server import store
    from uar.core.effectiveness_ranking import compute_effectiveness

    outcomes = store.get_outcomes(limit=50000)
    metadata = store.get_recommendation_metadata(limit=50000)
    return compute_effectiveness(outcomes, metadata)


@router.get("/api/uar/recommendations/calibration")
async def get_recommendation_calibration(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Recommendation calibration metrics.

    Omega-6b: Reliability buckets showing whether predicted confidence
    matches actual resolution rates.  Positive calibration_error means
    the system is overconfident; negative means underconfident.
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

    from uar.api.server import store
    from uar.core.calibration import compute_calibration

    outcomes = store.get_outcomes(limit=50000)
    metadata = store.get_recommendation_metadata(limit=50000)
    return compute_calibration(outcomes, metadata)


@router.post("/api/uar/recommendations/feedback")
async def post_recommendation_feedback(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Record operator feedback on a recommendation.

    Omega-5.2: Operator Feedback Loop.
    Accepts: { "recommendation_id": "...", "action": "accept|reject|dismiss" }
    Returns: { "ok": true, "recorded_at": ... }
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

    rec_id = body.get("recommendation_id")
    action = body.get("action")
    if not rec_id or not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_field",
                "message": "recommendation_id and action are required",
            },
        )
    if action not in ("accept", "reject", "dismiss"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_action",
                "message": "action must be accept, reject, or dismiss",
            },
        )

    user = user_info.get("user") if user_info else None
    store.record_feedback(rec_id, action, user_id=user)
    return {"ok": True, "recorded_at": time.time()}


@router.post("/api/uar/recommendations/outcome")
async def post_recommendation_outcome(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Record an outcome for a previously accepted recommendation.

    Omega-5.5: Outcome Attribution.
    Accepts: {
        "recommendation_id": "...",
        "outcome_type": "resolved|recurred|unknown"
    }
    Returns: { "ok": true, "recorded_at": ... }
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

    rec_id = body.get("recommendation_id")
    outcome_type = body.get("outcome_type")
    if not rec_id or not outcome_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_field",
                "message": (
                    "recommendation_id and outcome_type are required"
                ),
            },
        )
    if outcome_type not in ("resolved", "recurred", "unknown"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_outcome_type",
                "message": (
                    "outcome_type must be resolved, recurred, or unknown"
                ),
            },
        )

    import time
    from uar.api.server import store

    store.record_outcome(rec_id, outcome_type)
    return {"ok": True, "recorded_at": time.time()}
