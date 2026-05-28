"""Cache and sandbox endpoints.

Extracted from server.py to reduce monolith size.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import security
from uar.api.responses import error_response

router = APIRouter()


@router.get("/api/cache/stats")
async def cache_stats_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return skill cache statistics."""
    from uar.core.skill_cache import get_skill_cache

    cache = get_skill_cache()
    if cache is None:
        return {
            "hits": 0,
            "misses": 0,
            "size": 0,
            "capacity": 0,
        }
    return cache.stats()


@router.post("/api/cache/invalidate")
async def cache_invalidate_endpoint(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Invalidate cache entries.  Omit 'skill' to clear all."""
    from uar.core.skill_cache import get_skill_cache

    cache = get_skill_cache()
    skill = body.get("skill")
    count = cache.invalidate(skill)
    return {"invalidated": count, "skill": skill}


@router.get("/api/sandbox/health")
async def sandbox_health_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return WASM sandbox health."""
    from uar.core.sandbox import WASMSandbox

    return WASMSandbox().health()


@router.post("/api/sandbox/eval")
async def sandbox_eval_endpoint(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Safely evaluate an arithmetic expression in the WASM sandbox."""
    from uar.core.sandbox import sandbox_eval
    import logging

    logger = logging.getLogger(__name__)

    expression = body.get("expression", "")
    try:
        result = sandbox_eval(expression)
        return {"status": "completed", "result": result}
    except Exception as exc:
        logger.warning("sandbox_eval failed: %s", exc)
        return error_response(
            400, "eval_failed", "Expression evaluation failed"
        )
