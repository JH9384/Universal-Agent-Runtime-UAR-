"""Circuit breaker state router for operator dashboard.

Exposes real-time circuit breaker health so operators can see
which external services are degraded or unavailable.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.routers.operator.common import require_operator
from uar.core.circuit_breaker_decorator import _circuit_breakers

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/circuit-breakers")
async def get_circuit_breaker_states(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return current state of all circuit breakers."""
    require_operator(credentials)
    states = {
        name: cb.snapshot()
        for name, cb in _circuit_breakers.items()
    }
    open_count = sum(
        1 for s in states.values() if s["state"] == "open"
    )
    half_open_count = sum(
        1 for s in states.values() if s["state"] == "half_open"
    )
    return {
        "breakers": states,
        "summary": {
            "total": len(states),
            "open": open_count,
            "half_open": half_open_count,
            "healthy": len(states) - open_count - half_open_count,
        },
    }
