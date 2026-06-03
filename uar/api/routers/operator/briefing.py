"""Morning Briefing router."""

from __future__ import annotations

import datetime
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _get_snapshot_for_day,
    _load_all_incidents,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/briefing")
async def get_briefing(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Aggregate daily operational intelligence for operators."""
    auth_middleware(credentials)

    drift_events = 0
    trust_drops = 0
    open_incidents = 0
    unresolved_count = 0
    top_trusted = None
    top_score = 0.0
    trust_stable = True

    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = await run_in_threadpool(
            compute_trust, outcomes, metadata
        )
        types = trust_result.get("recommendation_types", [])

        for t in types:
            if t.get("drift_penalty", 0) > 0:
                drift_events += 1
            score = t.get("trust_score", 0)
            if score > top_score:
                top_score = score
                top_trusted = t.get("type")

        yesterday = _get_snapshot_for_day(int(time.time()) - 86400)
        if yesterday and "trust" in yesterday:
            old_types = yesterday["trust"].get("recommendation_types", [])
            old_map = {t["type"]: t.get("trust_score", 0) for t in old_types}
            for t in types:
                old = old_map.get(t["type"], t.get("trust_score", 0))
                if t.get("trust_score", 0) < old - 0.10:
                    trust_drops += 1

        if trust_drops >= 3:
            trust_stable = False
    except Exception as exc:
        logger.warning("briefing trust computation failed: %s", exc)

    try:
        open_incidents = len(
            [i for i in _load_all_incidents() if i.get("status") != "resolved"]
        )
    except Exception:
        pass

    try:
        outcomes = store.get_outcomes(limit=5000)
        resolved_ids = {o.get("recommendation_id") for o in outcomes}
        metadata = store.get_recommendation_metadata(limit=5000)
        unresolved_count = sum(
            1
            for m in metadata
            if m.get("recommendation_id") not in resolved_ids
        )
    except Exception:
        pass

    greeting = _greeting_for_hour()

    return {
        "greeting": greeting,
        "generated_at": int(time.time()),
        "drift_events": drift_events,
        "trust_drops": trust_drops,
        "trust_stable": trust_stable,
        "open_incidents": open_incidents,
        "unresolved_recommendations": unresolved_count,
        "top_trusted_type": top_trusted,
        "top_trust_score": round(top_score, 2) if top_trusted else None,
        "summary_text": _build_narrative(
            greeting, drift_events, trust_drops, open_incidents, trust_stable
        ),
    }


def _greeting_for_hour() -> str:
    h = datetime.datetime.now().hour
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def _build_narrative(
    greeting: str,
    drift: int,
    drops: int,
    incidents: int,
    stable: bool,
) -> str:
    parts = [f"{greeting}."]
    if drift:
        parts.append(f"{drift} drift event(s).")
    if drops:
        parts.append(f"{drops} trust drop(s).")
    if incidents:
        parts.append(f"{incidents} open incident(s).")
    if stable and not drift and not drops:
        parts.append("Trust stable. No anomalies.")
    return " ".join(parts)
