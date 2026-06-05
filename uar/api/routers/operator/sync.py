"""Sync status and resync router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.admin_models import ResyncIn
from uar.api.routers.operator.common import (
    audit_admin_action,
    require_operator,
)
from uar.core.sync_monitor import get_sync_monitor

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/sync/status")
async def get_sync_status(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return sync health for all registered stores."""
    require_operator(credentials)
    monitor = get_sync_monitor()
    report = await run_in_threadpool(monitor.check_health)
    return report.to_dict()


@router.post("/api/uar/sync/resync")
async def post_resync(
    body: ResyncIn,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Manually resync a target store from a source store.

    Args:
        body: Resync request with target store and optional source.
    """
    user_info = require_operator(credentials)
    monitor = get_sync_monitor()
    result = await run_in_threadpool(
        monitor.resync, body.target, body.source
    )
    audit_admin_action(
        user_info=user_info,
        action="POST /api/uar/sync/resync",
        resource=f"sync:{body.target}",
        outcome="success" if result.get("success") else "failure",
        details={"copied": result.get("copied", 0), "source": body.source},
    )
    return result
