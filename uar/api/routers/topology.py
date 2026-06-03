"""Topology analytics router — Phase D operational analytics.

Cross-run correlation, historical trends, and topology intelligence.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware

router = APIRouter()
security = HTTPBearer(auto_error=False)


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
    from uar.api.server import store

    cutoff = time.time() - (hours * 3600)
    runs = store.list_records(limit=50000)

    # Group by goal_id
    goal_groups: Dict[str, list] = {}
    for r in runs:
        if r.get("created_at", 0) < cutoff:
            continue
        gid = r.get("goal_id") or "no_goal"
        goal_groups.setdefault(gid, []).append(r)

    # Filter groups with min_runs
    correlations = []
    for gid, group in goal_groups.items():
        if len(group) < min_runs:
            continue

        statuses = [r.get("status") for r in group]
        failures = sum(1 for s in statuses if s and "fail" in str(s).lower())

        # Shared skills
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

        common_skills = set.intersection(*skill_sets) if skill_sets else set()
        all_skills = set.union(*skill_sets) if skill_sets else set()

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
                    (max(r.get("created_at", 0) for r in group) -
                     min(r.get("created_at", 0) for r in group))
                    / 3600,
                    2,
                ),
            }
        )

    correlations.sort(key=lambda x: x["failure_rate"], reverse=True)

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
    from uar.api.server import store

    cutoff = time.time() - (hours * 3600)
    runs = store.list_records(limit=50000)

    bucket_sizes = {"hour": 3600, "day": 86400, "week": 604800}
    bucket_size = bucket_sizes.get(interval, 86400)

    buckets: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {
            "run_count": 0,
            "failures": 0,
            "unique_skills": set(),
            "unique_goals": set(),
        }
    )

    for r in runs:
        ts = r.get("created_at", 0)
        if ts < cutoff:
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
        except Exception:
            pass

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

    return {
        "generated_at": time.time(),
        "hours": hours,
        "interval": interval,
        "trends": trend_list,
    }
