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
    cutoff = time.time() - (hours * 3600)

    # 1. Confidence trend from MC history
    mc_window = [s for s in _MC_HISTORY if s.get("timestamp", 0) >= cutoff]
    conf_scores = [
        s.get("replay_confidence", {}).get("score")
        for s in mc_window
        if s.get("replay_confidence") and
        s["replay_confidence"].get("score") is not None
    ]

    if len(conf_scores) >= 2:
        current_score = conf_scores[-1]
        previous_score = conf_scores[0]
    elif len(conf_scores) == 1:
        current_score = conf_scores[0]
        previous_score = current_score
    else:
        current_score = None
        previous_score = None

    delta = (
        (current_score or 0) - (previous_score or 0)
        if current_score is not None and previous_score is not None
        else 0
    )

    if delta > 5:
        state = "improving"
    elif delta < -5:
        state = "degrading"
    else:
        state = "stable"

    # 2. Failure contributors from recent runs
    all_runs = store.list_records(user_id=user if is_admin else user)
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    skill_failures: dict[str, int] = {}
    error_failures: dict[str, int] = {}
    for run in recent_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue
        for ev in run.get("events") or []:
            if ev.get("error") or ev.get("type") == "error":
                skill = ev.get("skill", "unknown")
                err = str(ev.get("error", ev.get("message", "unknown")))
                skill_failures[skill] = skill_failures.get(skill, 0) + 1
                err_key = err[:60]
                error_failures[err_key] = error_failures.get(err_key, 0) + 1

    top_skill_failures = sorted(
        skill_failures.items(), key=lambda x: x[1], reverse=True
    )[:5]
    top_error_failures = sorted(
        error_failures.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # 3. Burn-in contributor
    burnin_window = [
        r for r in _BURNIN_HISTORY
        if r.get("timestamp", 0) >= cutoff
    ]
    burnin_delta = 0
    if len(burnin_window) >= 2:
        burnin_delta = (
            burnin_window[-1].get("score", 0)
            - burnin_window[0].get("score", 0)
        )

    # 4. Build contributors
    contributors = []
    if state == "degrading":
        for skill, count in top_skill_failures:
            contributors.append({
                "name": f"{skill} failures",
                "impact": -count,
                "type": "failure",
            })
        for err, count in top_error_failures:
            contributors.append({
                "name": err[:40] + ("…" if len(err) > 40 else ""),
                "impact": -count,
                "type": "error",
            })
        if burnin_delta < 0:
            contributors.append({
                "name": "Burn-In drop",
                "impact": burnin_delta,
                "type": "evidence",
            })
    elif state == "improving":
        if top_skill_failures:
            contributors.append({
                "name": "Fewer skill failures",
                "impact": delta,
                "type": "failure",
            })
        if burnin_delta > 0:
            contributors.append({
                "name": "Burn-In improvement",
                "impact": burnin_delta,
                "type": "evidence",
            })
    else:
        contributors.append({
            "name": "No significant change",
            "impact": 0,
            "type": "stable",
        })

    # Cap contributors
    contributors = contributors[:5]

    return {
        "window_hours": hours,
        "current_score": current_score,
        "previous_score": previous_score,
        "delta": delta,
        "state": state,
        "confidence_history": conf_scores,
        "top_contributors": contributors,
        "failure_summary": {
            "total_failures": sum(skill_failures.values()),
            "top_skills": [
                {"skill": s, "count": c} for s, c in top_skill_failures
            ],
        },
    }
