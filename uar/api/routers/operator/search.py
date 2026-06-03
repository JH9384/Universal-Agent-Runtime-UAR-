"""Operational Search router."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

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
    """Unified search across runs, incidents, recommendations,
    snapshots, alerts."""
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False
    query = q.lower().strip()
    wanted_types = set(types.split(",") if types else [])

    def _do_search(user_id, admin, search_query, type_filter, result_limit):
        results: List[Dict[str, Any]] = []

        def add_result(
            rtype: str, obj: Dict[str, Any], score: int = 1
        ) -> None:
            if type_filter and rtype not in type_filter:
                return
            obj["_result_type"] = rtype
            obj["_score"] = score
            results.append(obj)

        try:
            runs = store.list_records(
                user_id=None if admin else user_id, limit=500
            )
            for r in runs:
                rid = str(getattr(r, "run_id", r.get("run_id", "")))
                if search_query in rid.lower():
                    add_result(
                        "run",
                        {
                            "id": rid,
                            "status": getattr(r, "status", "unknown"),
                        },
                        score=10,
                    )
        except Exception as _exc:
            logger.warning("Search: run lookup failed: %s", _exc)

        for inc in _load_all_incidents():
            hay = (
                f"{inc.get('title', '')} {inc.get('description', '')} "
                f"{inc.get('id', '')}"
            )
            if search_query in hay.lower():
                add_result("incident", inc, score=8)

        try:
            metadata = store.get_recommendation_metadata(limit=5000)
            for m in metadata:
                hay = (
                    f"{m.get('title', '')} {m.get('category', '')} "
                    f"{m.get('recommendation_id', '')}"
                )
                if search_query in hay.lower():
                    add_result("recommendation", m, score=7)
        except Exception as _exc:
            logger.warning("Search: recommendation metadata failed: %s", _exc)

        for snap in _load_all_snapshots(limit=50):
            ts_str = str(snap.get("timestamp", ""))
            run_ids = snap.get("recent_run_ids", [])
            if search_query in ts_str or any(
                search_query in str(r).lower() for r in run_ids
            ):
                add_result("snapshot", snap, score=5)

        try:
            for i in range(50):
                key = f"alert_tracker:alert-{i}"
                raw = store.get_metadata(key)
                if raw:
                    ev = json.loads(raw) if isinstance(raw, str) else raw
                    hay = f"{ev.get('type', '')} {ev.get('message', '')}"
                    if search_query in hay.lower():
                        add_result("alert", ev, score=6)
        except Exception as _exc:
            logger.warning("Search: alert metadata failed: %s", _exc)

        for item in _load_all_inbox_items():
            hay = f"{item.get('title', '')} {item.get('category', '')}"
            if search_query in hay.lower():
                add_result("inbox", item, score=6)

        results.sort(key=lambda x: -x.get("_score", 0))
        return {
            "query": q,
            "count": len(results),
            "results": results[:result_limit],
        }

    return await run_in_threadpool(
        _do_search, user, is_admin, query, wanted_types, limit
    )
