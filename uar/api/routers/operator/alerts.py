"""Alert tracker router for operator dashboard.

Surfaces webhook alert accuracy metrics so operators can see
response rates and unresolved alerts.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.alert_tracker import get_alert_tracker
from uar.api.routers.operator.common import require_operator

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/alerts")
async def get_alerts(
    hours: int = 168,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return webhook alert accuracy metrics.

    Args:
        hours: Lookback window (default 7 days).
    """
    require_operator(credentials)
    tracker = get_alert_tracker()
    metrics = tracker.get_accuracy_metrics(hours=hours)
    recent = tracker._pending[-50:]  # last 50 in-memory alerts
    return {
        "metrics": metrics,
        "recent_alerts": [
            {
                "id": e["id"],
                "alert_type": e["alert_type"],
                "severity": e["severity"],
                "message": e["message"],
                "fired_at": e["fired_at"],
                "status": e.get("status", "fired"),
            }
            for e in recent
        ],
    }
