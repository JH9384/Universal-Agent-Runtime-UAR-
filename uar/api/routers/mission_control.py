"""Mission Control API endpoint for the UAR Trust Spine.

Trust Spine Phase: T5
Issues: #72, #55
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.core.mission_control import build_snapshot
from uar.core.runtime_health import build_runtime_snapshot

security = HTTPBearer(auto_error=False)

router = APIRouter()


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
    return mc_snapshot.to_dict()
