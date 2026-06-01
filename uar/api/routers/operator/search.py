"""Operational Search router."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _load_all_incidents,
    _load_all_inbox_items,
    _load_all_snapshots,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/search")
async def search_all(
    q: str = Query(..., min_length=1),
    types: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Unified search across runs, incidents, recommendations, snapshots, alerts."""
    auth_middleware(credentials)
    query = q.lower().strip()
    wanted_types = set(types.split(",") if types else [])
    results: List[Dict[str, Any]] = []

    def add_result(rtype: str, obj: Dict[str, Any], score: int = 1) -> None:
        if wanted_types and rtype not in wanted_types:
            return
        obj["_result_type"] = rtype
        obj["_score"] = score
        results.append(obj)

    try:
        runs = store.list_records(limit=500)
        for r in runs:
            rid = str(getattr(r, "run_id", r.get("run_id", "")))
            if query in rid.lower():
                add_result(
                    "run",
                    {"id": rid, "status": getattr(r, "status", "unknown")},
                    score=10,
                )
    except Exception:
        pass

    for inc in _load_all_incidents():
        hay = f"{inc.get('title', '')} {inc.get('description', '')} {inc.get('id', '')}"
        if query in hay.lower():
            add_result("incident", inc, score=8)

    try:
        metadata = store.get_recommendation_metadata(limit=5000)
        for m in metadata:
            hay = f"{m.get('title', '')} {m.get('category', '')} {m.get('recommendation_id', '')}"
            if query in hay.lower():
                add_result("recommendation", m, score=7)
    except Exception:
        pass

    for snap in _load_all_snapshots(limit=50):
        ts_str = str(snap.get("timestamp", ""))
        run_ids = snap.get("recent_run_ids", [])
        if query in ts_str or any(query in str(r).lower() for r in run_ids):
            add_result("snapshot", snap, score=5)

    try:
        for i in range(50):
            key = f"alert_tracker:alert-{i}"
            raw = store.get_metadata(key)
            if raw:
                ev = json.loads(raw) if isinstance(raw, str) else raw
                hay = f"{ev.get('type', '')} {ev.get('message', '')}"
                if query in hay.lower():
                    add_result("alert", ev, score=6)
    except Exception:
        pass

    for item in _load_all_inbox_items():
        hay = f"{item.get('title', '')} {item.get('category', '')}"
        if query in hay.lower():
            add_result("inbox", item, score=6)

    results.sort(key=lambda x: -x.get("_score", 0))
    return {
        "query": q,
        "count": len(results),
        "results": results[:limit],
    }
