"""GDPR / privacy API router (T12).

Endpoints:
- GET  /api/uar/privacy/policy   — privacy policy metadata
- GET  /api/uar/privacy/export    — data portability export
- DELETE /api/uar/privacy/erase   — right to erasure
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import auth_middleware, security
from uar.api.responses import error_detail_response, success_response
from uar.core.gdpr import GDPRController
from uar.memory.base_store import get_store

router = APIRouter()


def _get_controller() -> GDPRController:
    return GDPRController(get_store())


@router.get("/api/uar/privacy/policy")
async def privacy_policy():
    """Privacy policy metadata (no auth required)."""
    ctrl = _get_controller()
    return success_response(data=ctrl.policy_metadata())


@router.get("/api/uar/privacy/export")
async def privacy_export(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Export all data for the authenticated user (data portability)."""
    user_info = auth_middleware(credentials)
    if not user_info:
        return error_detail_response(
            status_code=401,
            error="unauthorized",
            message="Authentication required",
        )
    user_id = user_info.get("user", "anonymous")
    ctrl = _get_controller()
    return success_response(data=ctrl.export_data(user_id))


@router.delete("/api/uar/privacy/erase")
async def privacy_erase(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Erase all data for the authenticated user (right to erasure)."""
    user_info = auth_middleware(credentials)
    if not user_info:
        return error_detail_response(
            status_code=401,
            error="unauthorized",
            message="Authentication required",
        )
    user_id = user_info.get("user", "anonymous")
    ctrl = _get_controller()
    removed = ctrl.erase_data(user_id)
    return success_response(
        data={"status": "erased", "removed_records": removed}
    )
