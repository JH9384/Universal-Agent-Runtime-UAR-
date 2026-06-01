"""Replay confidence endpoints for the UAR Trust Spine."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.core.replay_confidence import score_replay
from uar.memory.base_store import run_record_from_dict

router = APIRouter()
security = HTTPBearer(auto_error=False)


@router.get("/api/uar/runs/{run_id}/confidence")
async def get_run_confidence(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return Replay Confidence report for a historical run."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )
    user = user_info.get("user")
    is_admin = user_info.get("tier") == "admin"

    record = store.get_by_run_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Run not found"},
        )

    owner = record.get("user_id") or record.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    run_record = run_record_from_dict(record)
    return score_replay(run_record).to_dict()
