"""Topology analytics router — Phase D operational analytics.

Cross-run correlation, historical trends, and topology intelligence.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.state import store

router = APIRouter()
security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


@router.get("/api/uar/topology/correlation")
async def topology_correlation(
    hours: int = Query(168, ge=1, le=720),
    min_runs: int = Query(2, ge=1, le=100),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Cross-run correlation by goal_id.

    Groups runs by goal_id and identifies correlated failures,
    shared skill patterns, and execution divergence.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time

    user = user_info.get("user")
    is_admin = user_info.get("tier") == "admin"
    cutoff = time.time() - (hours * 3600)
    runs = store.list_records(
        user_id=None if is_admin else user, limit=50000
    )

    def _correlate(records, ts_cutoff, min_runs_req):
        goal_groups: Dict[str, list] = {}
        for r in records:
            if r.get("created_at", 0) < ts_cutoff:
                continue
            gid = r.get("goal_id") or "no_goal"
            goal_groups.setdefault(gid, []).append(r)

        correlations = []
        for gid, group in goal_groups.items():
            if len(group) < min_runs_req:
                continue

            statuses = [r.get("status") for r in group]
            failures = sum(
                1 for s in statuses if s and "fail" in str(s).lower()
            )

            skill_sets = []
            for r in group:
                skills = r.get("skills", "[]")
                try:
                    import json
                    skill_list = json.loads(skills)
                    if isinstance(skill_list, list):
                        skill_sets.append(set(skill_list))
                    else:
                        skill_sets.append(set())
                except Exception:
                    skill_sets.append(set())

            common_skills = (
                set.intersection(*skill_sets) if skill_sets else set()
            )
            all_skills = (
                set.union(*skill_sets) if skill_sets else set()
            )

            correlations.append(
                {
                    "goal_id": gid,
                    "run_count": len(group),
                    "failure_count": failures,
                    "failure_rate": round(failures / len(group), 4),
                    "common_skills": (
                        sorted(common_skills) if common_skills else None
                    ),
                    "unique_skill_count": len(all_skills),
                    "time_span_hours": round(
                        (
                            max(r.get("created_at", 0) for r in group) -
                            min(r.get("created_at", 0) for r in group)
                        )
                        / 3600,
                        2,
                    ),
                }
            )

        correlations.sort(key=lambda x: x["failure_rate"], reverse=True)
        return correlations, goal_groups

    correlations, goal_groups = await run_in_threadpool(
        _correlate, runs, cutoff, min_runs
    )

    return {
        "generated_at": time.time(),
        "hours": hours,
        "min_runs": min_runs,
        "correlated_goals": correlations[:50],
        "total_goals": len(goal_groups),
    }


@router.get("/api/uar/topology/trends")
async def topology_trends(
    hours: int = Query(168, ge=1, le=720),
    interval: str = Query("day", pattern="^(hour|day|week)$"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Historical trends of run volume, failure rate, and topology usage."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time
    from collections import defaultdict

    user = user_info.get("user")
    is_admin = user_info.get("tier") == "admin"
    cutoff = time.time() - (hours * 3600)
    runs = store.list_records(
        user_id=None if is_admin else user, limit=50000
    )

    def _trends(records, ts_cutoff, interval_key):
        bucket_sizes = {"hour": 3600, "day": 86400, "week": 604800}
        bucket_size = bucket_sizes.get(interval_key, 86400)

        buckets: Dict[int, Dict[str, Any]] = defaultdict(
            lambda: {
                "run_count": 0,
                "failures": 0,
                "unique_skills": set(),
                "unique_goals": set(),
            }
        )

        for r in records:
            ts = r.get("created_at", 0)
            if ts < ts_cutoff:
                continue
            bucket = int(ts // bucket_size) * bucket_size
            b = buckets[bucket]
            b["run_count"] += 1
            if r.get("status") and "fail" in str(r["status"]).lower():
                b["failures"] += 1
            b["unique_goals"].add(r.get("goal_id") or "none")
            try:
                import json
                skills = json.loads(r.get("skills", "[]"))
                if isinstance(skills, list):
                    b["unique_skills"].update(skills)
            except Exception as _exc:
                logger.debug("Topology: skill JSON parse failed: %s", _exc)

        trend_list = []
        for bucket_ts in sorted(buckets):
            b = buckets[bucket_ts]
            trend_list.append(
                {
                    "timestamp": bucket_ts,
                    "run_count": b["run_count"],
                    "failure_count": b["failures"],
                    "failure_rate": round(
                        b["failures"] / max(b["run_count"], 1), 4
                    ),
                    "unique_goals": len(b["unique_goals"]),
                    "unique_skills": len(b["unique_skills"]),
                }
            )
        return trend_list

    trend_list = await run_in_threadpool(_trends, runs, cutoff, interval)

    return {
        "generated_at": time.time(),
        "hours": hours,
        "interval": interval,
        "trends": trend_list,
    }


# Deferred import to avoid circular dependency at module load time.
_ANALYTICS_CACHE = None


def _analytics_cache():
    global _ANALYTICS_CACHE
    if _ANALYTICS_CACHE is None:
        from uar.core.analytics_cache import ANALYTICS_CACHE
        _ANALYTICS_CACHE = ANALYTICS_CACHE
    return _ANALYTICS_CACHE


@router.get("/api/uar/topology/analytics")
async def get_topology_analytics(
    mode: str = Query("success", pattern="^(success|failure)$"),
    hours: int = Query(168, ge=1, le=720),
    top: int = Query(15, ge=1, le=50),
    limit: int = Query(50000, ge=1, le=50000),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Consolidated topology analytics.

    D4A-2 — Endpoint Consolidation.
    Replaces separate hot-paths and failure-hotspots endpoints
    with a single mode-driven analytics endpoint.

    Modes:
      success → Skill nodes/edges ranked by invocation volume.
      failure → Skill nodes/edges ranked by failure rate.

    Recipe data removed from topology; link to Recipe Intelligence
    is provided instead.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    import time

    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    cache_key = f"topology-analytics-{mode}"
    cached = _analytics_cache().get(
        cache_key, user, is_admin, hours, limit
    )
    if cached is not None:
        return cached

    cutoff = time.time() - (hours * 3600)

    all_runs = store.list_records(
        user_id=None if is_admin else user, limit=limit
    )
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    from uar.core.analytics_snapshot import (
        build_analytics_snapshot,
        extract_failure_hotspots,
        extract_topology_hot_paths,
    )

    snapshot = build_analytics_snapshot(
        recent_runs, user, is_admin, hours, limit
    )

    if mode == "success":
        result = extract_topology_hot_paths(snapshot, top)
        # Remove recipe table; link to Recipe Intelligence
        result.pop("recipes", None)
        result["recipe_intelligence_link"] = "/api/uar/recipes/intelligence"
    else:
        result = extract_failure_hotspots(snapshot, top)

    result["meta"] = {
        "mode": mode,
        "runs_loaded": len(all_runs),
        "runs_analyzed": snapshot.runs_analyzed,
        "limit": limit,
        "truncated": len(all_runs) >= limit,
    }
    _analytics_cache().set(
        cache_key, user, is_admin, hours, limit, result
    )
    return result
