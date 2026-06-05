"""Data source registry router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.admin_models import (
    AdminActionOut,
    DataSourceIn,
)
from uar.api.routers.operator.common import (
    audit_admin_action,
    require_operator,
)
from uar.core.data_source_registry import get_data_source_registry

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/data-sources")
async def get_data_sources(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return all registered data sources."""
    require_operator(credentials)
    reg = get_data_source_registry()
    sources = await run_in_threadpool(reg.list_sources)
    return {
        "sources": [s.to_dict() for s in sources],
        "total": len(sources),
        "healthy": sum(1 for s in sources if s.healthy),
    }


@router.post("/api/uar/data-sources")
async def post_data_source(
    body: DataSourceIn,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Register a new data source."""
    user_info = require_operator(credentials)
    reg = get_data_source_registry()
    source = await run_in_threadpool(
        reg.register,
        body.dsid,
        body.source_type,
        body.location,
        body.description,
    )
    audit_admin_action(
        user_info=user_info,
        action="POST /api/uar/data-sources",
        resource=f"datasource:{body.dsid}",
        outcome="success",
        details={"source_type": body.source_type, "location": body.location},
    )
    return source.to_dict()


@router.delete("/api/uar/data-sources/{dsid}")
async def delete_data_source(
    dsid: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Deregister a data source."""
    user_info = require_operator(credentials)
    reg = get_data_source_registry()
    existed = await run_in_threadpool(reg.deregister, dsid)
    audit_admin_action(
        user_info=user_info,
        action="DELETE /api/uar/data-sources",
        resource=f"datasource:{dsid}",
        outcome="success" if existed else "not_found",
    )
    return AdminActionOut(
        success=True, id=dsid, deleted=existed,
        message=(
            f"Data source '{dsid}' deleted."
            if existed else f"Data source '{dsid}' not found."
        ),
    ).model_dump()


@router.post("/api/uar/data-sources/{dsid}/check")
async def check_data_source(
    dsid: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Run a health check on a data source."""
    require_operator(credentials)
    reg = get_data_source_registry()
    source = await run_in_threadpool(reg.check_health, dsid)
    return source.to_dict()
