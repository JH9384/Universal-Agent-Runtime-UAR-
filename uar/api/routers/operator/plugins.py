"""Plugin lifecycle router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.common import (
    audit_admin_action,
    require_operator,
)
from uar.skills.plugin import get_plugin_manifests, reload_plugins

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/plugins")
async def get_plugins(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return all loaded plugin manifests with health status."""
    require_operator(credentials)
    manifests = get_plugin_manifests()
    return {
        "plugins": [m.to_dict() for m in manifests],
        "total": len(manifests),
        "healthy": sum(1 for m in manifests if m.healthy),
    }


@router.post("/api/uar/plugins/reload")
async def post_reload_plugins(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Reload all plugins from disk and PyPI entry points."""
    user_info = require_operator(credentials)
    results = await run_in_threadpool(reload_plugins)
    manifests = get_plugin_manifests()
    audit_admin_action(
        user_info=user_info,
        action="POST /api/uar/plugins/reload",
        resource="plugins:all",
        outcome="success",
        details={"loaded": len(results)},
    )
    return {
        "success": True,
        "loaded": results,
        "plugins": [m.to_dict() for m in manifests],
        "total": len(manifests),
        "healthy": sum(1 for m in manifests if m.healthy),
    }
