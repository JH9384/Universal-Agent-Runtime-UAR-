"""Replay Explorer API endpoint for the UAR Trust Spine.

Bundles timeline, events, replay confidence, and failure path into a
single operator-facing view of a specific run.

Trust Spine Phase: T6
Issue: #56
Spec: docs/operations/REPLAY_EXPLORER.md
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.core.replay_confidence import score_replay
from uar.core.timeline import timeline_from_record
from uar.memory.base_store import run_record_from_dict

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.get("/api/uar/runs/{run_id}/explorer")
async def get_replay_explorer(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return a full Replay Explorer bundle for a specific run.

    Combines:
    - summary (status, skills, goal)
    - timeline (event sequence)
    - confidence (T1 replay confidence)
    - failure_path (events with errors)
    - events (raw event list)

    Access control: admins see any run; non-admins see only their own.
    """
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

    raw = store.get_by_run_id(run_id)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "run_not_found",
                "message": f"Run {run_id!r} not found",
            },
        )

    owner = raw.get("user_id") or raw.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    try:
        record = run_record_from_dict(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "record_parse_error",
                "message": str(exc),
            },
        ) from exc

    summary = {
        "run_id": run_id,
        "goal_id": raw.get("goal_id"),
        "status": raw.get("status"),
        "skills": raw.get("skills", []),
        "created_at": raw.get("created_at"),
    }

    try:
        timeline = timeline_from_record(record)
    except Exception as exc:
        logger.warning(
            "timeline_from_record failed for run %s: %s", run_id, exc
        )
        timeline = {}

    try:
        rc_report = score_replay(record)
        confidence = rc_report.to_dict().get("confidence", {})
    except Exception as exc:
        logger.warning(
            "score_replay failed for run %s: %s", run_id, exc
        )
        confidence = {}

    failure_path = [
        ev for ev in (record.events or [])
        if ev.get("error") or ev.get("type") == "error"
    ]

    return {
        "run_id": run_id,
        "summary": summary,
        "timeline": timeline,
        "confidence": confidence,
        "failure_path": failure_path,
        "events": list(record.events or []),
    }
