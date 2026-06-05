"""Self-update router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.common import require_operator
from uar.core.self_update import check_for_update

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/update/status")
async def get_update_status(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return UAR self-update availability status."""
    require_operator(credentials)
    status = await run_in_threadpool(check_for_update)
    return status.to_dict()
