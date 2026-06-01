"""Recipe CRUD endpoints.

Extracted from server.py to reduce monolith size.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import security
from uar.services import AuthService, RecipeService

router = APIRouter()

_recipe_svc = RecipeService()
_auth_svc = AuthService()


def _recipe_http_error(
    exc: Exception, recipe_id: str, *, creating: bool = False
) -> HTTPException:
    """Map RecipeService exceptions to HTTP status codes."""
    msg = str(exc)
    if "canonical" in msg.lower():
        return HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if creating
                else status.HTTP_403_FORBIDDEN
            ),
            detail={
                "error": "conflict" if creating else "forbidden",
                "message": (
                    "Recipe already exists"
                    if creating
                    else "Recipe is canonical and cannot be modified"
                ),
            },
        )
    if "skills must be" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_skills",
                "message": "Invalid skills in recipe",
            },
        )
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": "Recipe not found",
            },
        )
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Not owner"},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": "internal", "message": "Internal server error"},
    )


@router.get("/api/uar/recipes")
async def get_recipes(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return canonical + user-created recipe definitions."""
    user_info = _auth_svc.authenticate(credentials)
    recipes = _recipe_svc.list_all(
        user_id=user_info.get("user") if user_info else None
    )
    return {"recipes": recipes}


@router.post("/api/uar/recipes")
async def create_recipe(
    recipe: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Create a new user recipe."""
    user = _auth_svc.require_user(credentials)
    recipe_id = recipe.get("id")
    if not recipe_id or not isinstance(recipe_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_id",
                "message": "Recipe must have an 'id' string",
            },
        )
    try:
        _recipe_svc.create(recipe_id, recipe, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id, creating=True) from exc
    return {"created": recipe_id}


@router.put("/api/uar/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    recipe: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Update an existing user recipe."""
    user = _auth_svc.require_user(credentials)
    try:
        _recipe_svc.update(recipe_id, recipe, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id) from exc
    return {"updated": recipe_id}


@router.delete("/api/uar/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Delete a user recipe."""
    user = _auth_svc.require_user(credentials)
    try:
        _recipe_svc.delete(recipe_id, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id) from exc
    return {"deleted": recipe_id}


@router.get("/api/uar/recipes/intelligence")
async def get_recipe_intelligence(
    hours: int = Query(168, ge=1, le=720),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Derive recipe performance intelligence from run records.

    Issue #97 — Phase D3.3: Recipe Intelligence.
    Analyzes runs with execution_order metadata to produce
    recipe classifications: Recommended, Monitor, Retire Candidate.
    Zero new storage layer.
    """
    from uar.api.server import store

    user_info = _auth_svc.authenticate(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    import time
    cutoff = time.time() - (hours * 3600)

    all_runs = store.list_records(user_id=user if is_admin else user)
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    recipes: dict[str, dict] = {}

    for run in recent_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue

        status_ok = run.get("status") == "success"
        conf = run.get("replay_confidence") or run.get("confidence")
        if isinstance(conf, dict):
            conf = conf.get("score")
        conf_score = float(conf) if conf is not None else None
        dur = run.get("duration_ms", 0)
        ts = run.get("created_at") or run.get("timestamp", 0)
        meta = run.get("metadata") or {}
        exec_order = meta.get("execution_order") or []

        for item in exec_order:
            if isinstance(item, dict) and item.get("type") == "recipe":
                rid = item.get("content", item.get("id", "unknown"))
                if rid not in recipes:
                    recipes[rid] = {
                        "recipe": rid,
                        "executions": 0,
                        "successes": 0,
                        "failures": 0,
                        "confidence_sum": 0.0,
                        "confidence_count": 0,
                        "duration_sum": 0,
                        "duration_count": 0,
                        "last_execution": 0,
                    }
                rec = recipes[rid]
                rec["executions"] += 1
                if status_ok:
                    rec["successes"] += 1
                else:
                    rec["failures"] += 1
                if conf_score is not None:
                    rec["confidence_sum"] += conf_score
                    rec["confidence_count"] += 1
                if dur:
                    rec["duration_sum"] += dur
                    rec["duration_count"] += 1
                if ts > rec["last_execution"]:
                    rec["last_execution"] = ts

    # Build recipe list with derived metrics
    recipe_list = []
    for rec in recipes.values():
        total = rec["executions"]
        rec["success_rate"] = (
            round(rec["successes"] / total, 2) if total else 0
        )
        rec["failure_rate"] = round(
            rec["failures"] / total, 2
        ) if total else 0
        rec["avg_confidence"] = round(
            rec["confidence_sum"] / rec["confidence_count"], 2
        ) if rec["confidence_count"] else None
        rec["avg_duration_ms"] = int(
            rec["duration_sum"] / rec["duration_count"]
        ) if rec["duration_count"] else None

        # Classification
        sr = rec["success_rate"]
        fr = rec["failure_rate"]
        usage = rec["executions"]
        if sr >= 0.9 and usage >= 3:
            rec["classification"] = "recommended"
        elif fr >= 0.5 or (sr < 0.5 and usage >= 3):
            rec["classification"] = "retire"
        else:
            rec["classification"] = "monitor"

        recipe_list.append(rec)

    # Sort by classification priority, then by success rate desc
    priority = {"recommended": 0, "monitor": 1, "retire": 2}
    recipe_list.sort(
        key=lambda r: (
            priority.get(r["classification"], 1),
            -r["success_rate"],
        )
    )

    return {
        "hours": hours,
        "total_runs": len(recent_runs),
        "recipes": recipe_list,
    }
