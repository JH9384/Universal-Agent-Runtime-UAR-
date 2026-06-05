"""Maintenance window router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.admin_models import (
    AdminActionOut,
    MaintenanceWindowIn,
)
from uar.api.routers.operator.common import (
    audit_admin_action,
    require_operator,
)
from uar.core.maintenance import get_maintenance_manager

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/maintenance")
async def get_maintenance_windows(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return all scheduled maintenance windows."""
    require_operator(credentials)
    mgr = get_maintenance_manager()
    windows = await run_in_threadpool(mgr.list_windows)
    active = await run_in_threadpool(mgr.get_active_window)
    return {
        "windows": [w.to_dict() for w in windows],
        "active": active.to_dict() if active else None,
    }


@router.post("/api/uar/maintenance")
async def post_maintenance_window(
    body: MaintenanceWindowIn,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Schedule a new maintenance window."""
    user_info = require_operator(credentials)
    mgr = get_maintenance_manager()
    window = await run_in_threadpool(
        mgr.schedule,
        body.wid,
        body.start_at,
        body.end_at,
        body.description,
    )
    audit_admin_action(
        user_info=user_info,
        action="POST /api/uar/maintenance",
        resource=f"maintenance:{body.wid}",
        outcome="success",
        details={"start_at": body.start_at, "end_at": body.end_at},
    )
    return window.to_dict()


@router.delete("/api/uar/maintenance/{wid}")
async def delete_maintenance_window(
    wid: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Cancel a maintenance window."""
    user_info = require_operator(credentials)
    mgr = get_maintenance_manager()
    existed = await run_in_threadpool(mgr.cancel, wid)
    audit_admin_action(
        user_info=user_info,
        action="DELETE /api/uar/maintenance",
        resource=f"maintenance:{wid}",
        outcome="success" if existed else "not_found",
    )
    return AdminActionOut(
        success=True, id=wid, cancelled=existed,
        message=(
            f"Maintenance window '{wid}' cancelled."
            if existed else f"Window '{wid}' not found."
        ),
    ).model_dump()
