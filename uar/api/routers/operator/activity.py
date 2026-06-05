"""Activity log router for operator dashboard."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.common import require_operator
from uar.core.activity_log import get_activity_log_aggregator

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/activity")
async def get_activity(
    limit: int = Query(200, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=168),
    event_types: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return the operator activity log.

    Args:
        limit: Max events to return.
        hours: Only events from the last N hours.
        event_types: Comma-separated list of types to filter.
    """
    require_operator(credentials)
    aggregator = get_activity_log_aggregator()
    since = time.time() - (hours * 3600) if hours else None
    types = event_types.split(",") if event_types else None
    events = await run_in_threadpool(
        aggregator.get_activity,
        limit=limit,
        event_types=types,
        since=since,
    )
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "hours": hours,
    }
