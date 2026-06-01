"""Investigation Flow + Replay router."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _load_all_incidents,
    _load_all_investigations,
    _persist_investigation,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


# ------------------------------------------------------------------
# Unified Investigation Flow
# ------------------------------------------------------------------


@router.get("/api/uar/investigate/{run_id}")
async def investigate_run(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Begin guided investigation for a run."""
    auth_middleware(credentials)

    # Gather evidence
    record = None
    try:
        record = store.get_by_run_id(run_id)
    except Exception:
        pass

    recommendations = []
    try:
        metadata = store.get_recommendation_metadata(limit=5000)
        for m in metadata:
            if m.get("run_id") == run_id:
                recommendations.append(
                    {
                        "id": m.get("recommendation_id"),
                        "title": m.get("title"),
                        "confidence": m.get("confidence"),
                        "category": m.get("category"),
                    }
                )
    except Exception:
        pass

    # Check for linked incidents
    linked_incidents = [
        i
        for i in _load_all_incidents()
        if run_id in i.get("linked_run_ids", [])
    ]

    return {
        "run_id": run_id,
        "status": "investigating",
        "recommendations": recommendations,
        "linked_incidents": linked_incidents,
        "suggested_actions": _suggest_actions(record, recommendations),
    }


def _suggest_actions(record, recommendations: list) -> list:
    actions = []
    if not record:
        actions.append("Run not found — verify run_id.")
    if recommendations:
        actions.append("Review recommendations for this run.")
    actions.append("Check topology for downstream impact.")
    return actions


# ------------------------------------------------------------------
# Investigation Replay
# ------------------------------------------------------------------


@router.post("/api/uar/investigations")
async def create_investigation(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Start a new investigation session."""
    auth_middleware(credentials)
    import uuid

    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    inv = {
        "id": inv_id,
        "title": body.get("title", "Untitled Investigation"),
        "run_id": body.get("run_id"),
        "incident_id": body.get("incident_id"),
        "started_at": now,
        "ended_at": None,
        "actions": [],
        "status": "active",
    }
    _persist_investigation(inv)
    return inv


@router.get("/api/uar/investigations")
async def list_investigations(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List all investigation sessions."""
    auth_middleware(credentials)
    return _load_all_investigations()


@router.get("/api/uar/investigations/{inv_id}")
async def get_investigation(
    inv_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a single investigation session."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            return inv
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )


@router.put("/api/uar/investigations/{inv_id}")
async def end_investigation(
    inv_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """End an investigation session."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            inv["status"] = body.get("status", "closed")
            inv["ended_at"] = int(time.time())
            inv["conclusion"] = body.get("conclusion", "")
            _persist_investigation(inv)
            return inv
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )


@router.post("/api/uar/investigations/{inv_id}/actions")
async def record_action(
    inv_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Record an action during an investigation."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            action = {
                "type": body.get("type", "note"),
                "data": body.get("data", {}),
                "timestamp": int(time.time()),
            }
            inv.setdefault("actions", []).append(action)
            _persist_investigation(inv)
            return action
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )
