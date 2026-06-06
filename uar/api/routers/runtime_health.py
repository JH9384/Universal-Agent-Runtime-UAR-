"""Runtime Health API endpoint for the UAR Trust Spine.

Trust Spine Phase: T2
Issue: #83
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.state import store
from uar.core.runtime_health import (
    build_runtime_snapshot,
    score_runtime_health,
)

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.get("/api/uar/health/runtime")
async def get_runtime_health(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return a Runtime Health report derived from store and registry."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    from uar.core.registry import registry
    from uar.api.routers.burn_in import BurnInProxy

    snapshot = await run_in_threadpool(build_runtime_snapshot, store)
    report = await run_in_threadpool(
        score_runtime_health,
        registry=registry,
        burnin_report=BurnInProxy.from_latest(store=store),
        snapshot=snapshot,
    )
    return report.to_dict()
