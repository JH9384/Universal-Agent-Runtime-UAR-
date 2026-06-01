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
