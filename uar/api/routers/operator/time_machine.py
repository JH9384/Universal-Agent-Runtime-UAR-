"""Time Machine (snapshots) router."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _load_all_snapshots,
    _persist_snapshot,
    _snapshot_key,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/snapshots")
async def list_snapshots(
    limit: int = Query(24, ge=1, le=168),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List historical snapshots."""
    auth_middleware(credentials)
    return _load_all_snapshots(limit=limit)


@router.post("/api/uar/snapshots")
async def create_snapshot(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Capture a new operational snapshot."""
    auth_middleware(credentials)

    now = int(time.time())
    snap: dict = {"timestamp": now, "captured_at": now}

    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        snap["trust"] = compute_trust(outcomes, metadata)
    except Exception as exc:
        logger.warning("snapshot trust capture failed: %s", exc)
        snap["trust"] = None

    try:
        recs = store.get_recommendation_metadata(limit=5000)
        snap["recommendation_count"] = len(recs)
    except Exception:
        snap["recommendation_count"] = 0

    try:
        runs = store.list_records(limit=100)
        snap["recent_run_ids"] = [
            getattr(r, "run_id", r.get("run_id")) for r in runs[:10]
        ]
    except Exception:
        snap["recent_run_ids"] = []

    _persist_snapshot(snap)
    return snap


@router.get("/api/uar/snapshots/{timestamp}")
async def get_snapshot(
    timestamp: int,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a single snapshot by timestamp."""
    auth_middleware(credentials)
    key = _snapshot_key(timestamp)
    raw = store.get_metadata(key)
    if raw:
        import json

        return json.loads(raw) if isinstance(raw, str) else raw
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Snapshot not found",
    )


@router.get("/api/uar/snapshots/compare")
async def compare_snapshots(
    a: int,
    b: int,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Compare two snapshots."""
    auth_middleware(credentials)
    import json

    raw_a = store.get_metadata(_snapshot_key(a))
    raw_b = store.get_metadata(_snapshot_key(b))
    snap_a = json.loads(raw_a) if isinstance(raw_a, str) else raw_a
    snap_b = json.loads(raw_b) if isinstance(raw_b, str) else raw_b

    trust_a = (snap_a or {}).get("trust", {})
    trust_b = (snap_b or {}).get("trust", {})

    types_a = {
        t.get("type"): t for t in trust_a.get("recommendation_types", [])
    }
    types_b = {
        t.get("type"): t for t in trust_b.get("recommendation_types", [])
    }

    changes = []
    for t, data_b in types_b.items():
        data_a = types_a.get(t, {})
        score_a = data_a.get("trust_score", 0) or 0
        score_b = data_b.get("trust_score", 0) or 0
        if abs(score_b - score_a) > 0.05:
            changes.append(
                {
                    "type": t,
                    "trust_before": round(score_a, 3),
                    "trust_after": round(score_b, 3),
                    "delta": round(score_b - score_a, 3),
                }
            )

    rec_a = (snap_a or {}).get("recommendation_count", 0)
    rec_b = (snap_b or {}).get("recommendation_count", 0)

    return {
        "snapshot_a": a,
        "snapshot_b": b,
        "recommendation_delta": rec_b - rec_a,
        "trust_changes": changes,
    }


# Route ordering fix: static paths must precede dynamic /{timestamp} paths
_STATIC_FIRST_PATHS = {
    "/api/uar/snapshots/compare",
}

for _path in _STATIC_FIRST_PATHS:
    _static_idx = None
    _dynamic_idx = None
    for _i, _route in enumerate(router.routes):
        if getattr(_route, "path", None) == _path:
            _static_idx = _i
        if getattr(_route, "path", None) == "/api/uar/snapshots/{timestamp}":
            _dynamic_idx = _i
    if (
        _static_idx is not None
        and _dynamic_idx is not None
        and _static_idx > _dynamic_idx
    ):
        router.routes.insert(_dynamic_idx, router.routes.pop(_static_idx))
