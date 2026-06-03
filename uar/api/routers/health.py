"""Health, metrics, and status endpoints.

Extracted from server.py to reduce monolith size and provide a
self-contained router for observability endpoints.
"""

import os
import time
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import auth_middleware, security, _is_dev_mode
from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version

from uar.api.state import _uar_start_time

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """Health check endpoint (backwards-compatible alias for liveness)."""
    return {
        "status": "healthy",
        "version": get_uar_version(),
        "uor_upstream_version": get_uor_version(),
    }


@router.get("/api/status")
async def status_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Operational status with skill inventory and authenticated user."""
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else "anonymous"
    from uar.core.registry import registry

    return {
        "status": "operational",
        "available_skills": registry.list(),
        "user": user,
    }


@router.get("/api/health/live")
async def liveness_probe():
    """Kubernetes liveness probe — process is alive."""
    return {"status": "alive"}


@router.get("/api/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe — service is ready to accept traffic."""
    import asyncio

    checks = {}

    # Check disk writable
    _task = asyncio.current_task()
    _probe_id = id(_task) if _task else id(object())
    _runs_dir = os.path.abspath(os.getenv("RUNS_DIR", "runs"))
    os.makedirs(_runs_dir, exist_ok=True)
    _test_file = os.path.join(
        _runs_dir, f".health_check_{os.getpid()}_{_probe_id}"
    )
    try:
        with open(_test_file, "w") as f:
            f.write("ok")
        os.unlink(_test_file)
        checks["disk_writable"] = True
    except OSError:
        checks["disk_writable"] = False

    all_ready = all(v for k, v in checks.items() if isinstance(v, bool))
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
        },
    )


@router.get("/api/health/circuit-breakers")
async def health_circuit_breakers(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Circuit breaker health with per-service state and failure counts."""
    user_info = auth_middleware(credentials)
    if not user_info and not _is_dev_mode():
        return JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "error": "unauthorized",
                    "message": "Authentication required",
                }
            },
        )

    from uar.core.circuit_breaker_decorator import (
        get_circuit_breaker_details,
    )

    details = await get_circuit_breaker_details()
    any_open = any(info["state"] == "open" for info in details.values())

    status_code = 200 if not any_open else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if not any_open else "degraded",
            "circuits": details,
        },
    )


@router.post("/api/health/circuit-breakers/{service_name}/reset")
async def reset_circuit_breaker(
    service_name: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Reset a circuit breaker to closed state."""
    user_info = auth_middleware(credentials)
    if not user_info and not _is_dev_mode():
        return JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "error": "unauthorized",
                    "message": "Authentication required",
                }
            },
        )
    is_admin = user_info.get("tier") == "admin" if user_info else False
    if not is_admin and not _is_dev_mode():
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "error": "forbidden",
                    "message": "Admin access required",
                }
            },
        )

    from uar.core.circuit_breaker_decorator import (
        reset_circuit_breaker as _reset_cb,
        get_circuit_breaker_details,
    )

    details = await get_circuit_breaker_details()
    if service_name not in details:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "error": "not_found",
                    "message": f"Circuit breaker '{service_name}' not found",
                }
            },
        )

    await _reset_cb(service_name)
    return JSONResponse(
        status_code=200,
        content={"status": "reset", "service": service_name},
    )


@router.get("/api/health/dashboard")
async def health_dashboard(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Comprehensive health dashboard data for the web UI.

    Requires authentication in production; dev mode allows anonymous.
    """
    user_info = auth_middleware(credentials)
    if not user_info and not _is_dev_mode():
        return JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "error": "unauthorized",
                    "message": "Authentication required",
                }
            },
        )
    from uar.core.registry import registry
    from uar.core.circuit_breaker_decorator import (
        get_circuit_breaker_details,
    )

    skill_health = []
    for name in registry.list():
        try:
            registry.get(name)
            skill_health.append({"name": name, "available": True})
        except Exception:
            skill_health.append({
                "name": name,
                "available": False,
                "last_error": "Skill unavailable",
            })

    cb_details = await get_circuit_breaker_details()
    circuit_breakers = [
        {"name": name, **info}
        for name, info in cb_details.items()
    ]

    return {
        "skills": skill_health,
        "circuit_breakers": circuit_breakers,
        "recent_errors": [],
        "server_version": get_uar_version(),
        "uptime_seconds": int(time.time() - _uar_start_time),
    }
