"""Incident Workbench router."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _incident_key,
    _load_all_incidents,
    _persist_incident,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/incidents")
async def list_incidents(
    status: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List all incidents, optionally filtered by status."""
    auth_middleware(credentials)
    incidents = _load_all_incidents()
    if status:
        incidents = [i for i in incidents if i.get("status") == status]
    return incidents


@router.post("/api/uar/incidents")
async def create_incident(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Create a new incident."""
    auth_middleware(credentials)
    import uuid

    incident_id = f"incident-{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    incident = {
        "id": incident_id,
        "title": body.get("title", "Untitled Incident"),
        "description": body.get("description", ""),
        "status": body.get("status", "open"),
        "severity": body.get("severity", "medium"),
        "linked_run_ids": body.get("linked_run_ids", []),
        "linked_rec_ids": body.get("linked_rec_ids", []),
        "resolution_notes": body.get("resolution_notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    _persist_incident(incident)
    return incident


@router.get("/api/uar/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a single incident."""
    auth_middleware(credentials)
    for inc in _load_all_incidents():
        if inc.get("id") == incident_id:
            return inc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Incident not found",
    )


@router.put("/api/uar/incidents/{incident_id}")
async def update_incident(
    incident_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Update an incident."""
    auth_middleware(credentials)
    for inc in _load_all_incidents():
        if inc.get("id") == incident_id:
            for field in (
                "title",
                "description",
                "status",
                "severity",
                "linked_run_ids",
                "linked_rec_ids",
                "resolution_notes",
            ):
                if field in body:
                    inc[field] = body[field]
            inc["updated_at"] = int(time.time())
            _persist_incident(inc)
            return inc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Incident not found",
    )


@router.delete("/api/uar/incidents/{incident_id}")
async def delete_incident(
    incident_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Delete an incident."""
    auth_middleware(credentials)
    key = _incident_key(incident_id)
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, None)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, "null")
    except Exception:
        pass
    return {"deleted": incident_id}
