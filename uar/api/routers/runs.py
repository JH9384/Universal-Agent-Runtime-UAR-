"""Run execution and query endpoints for the UAR API."""

import logging
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.models import ErrorResponse, RunRequest, RunResponse
from uar.api.middleware import (
    auth_middleware,
    error_handler_middleware,
    rate_limit_middleware,
    request_logging_middleware,
    _extract_skill_from_request_data,
)
from uar.api.tracing import trace_span
from uar.core.exceptions import UARError, ValidationError
from uar.core.planner import SimplePlanner
from uar.core.replay import replay_summary
from uar.core.replay_confidence import score_replay
from uar.core.timeline import timeline_from_record
from uar.memory.base_store import run_record_from_dict

router = APIRouter()

logger = logging.getLogger("uar.api.runs")

security = HTTPBearer(auto_error=False)


@router.post(
    "/api/uar/run",
    response_model=RunResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@error_handler_middleware
async def run_goal(
    req: RunRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Execute a goal and return the complete result"""
    from uar.api.server import (
        _build_goal,
        _idempotency_get,
        _idempotency_set,
        store,
    )

    with trace_span("api.run_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting (pass parsed skill to avoid ASGI stream reuse)
        first_skill = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )
        rate_limit_middleware(request, credentials, first_skill=first_skill)

        # Get user info
        user_info = auth_middleware(credentials)

        # Log request
        request_id = request_logging_middleware(request, user_info)

        try:
            # Idempotency: return cached result for duplicate keys
            if req.idempotency_key:
                cached = _idempotency_get(req.idempotency_key)
                if cached is not None:
                    logger.info(
                        "[%s] Idempotency hit: %s",
                        request_id,
                        req.idempotency_key,
                    )
                    return cached

            goal = _build_goal(req)
            planner = SimplePlanner()
            strategy = planner.plan(goal)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            result = executor.run(strategy, goal, timeout_seconds=timeout)
            result.user_id = user_info.get("user") if user_info else None

            # Cache result for idempotency
            if req.idempotency_key:
                _idempotency_set(req.idempotency_key, result)

            store.append(result)
            logger.info(
                "[%s] Run completed successfully: %s",
                request_id,
                result.run_id,
            )

            return result

        except ValidationError as e:
            logger.warning("[%s] Validation error: %s", request_id, e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Validation error",
                    "message": e.user_message,
                    "field": e.field,
                    "request_id": request_id,
                    "suggestion": (
                        "Check your request parameters and try again. "
                        "For help, see the API documentation."
                    ),
                },
            ) from e
        except UARError as e:
            logger.error("[%s] UAR error: %s", request_id, e)
            error_type = type(e).__name__
            suggestion = "Please check your request and try again."
            if "Path" in error_type:
                suggestion = (
                    "Please verify the file path exists and is accessible."
                )
            elif "Permission" in error_type:
                suggestion = "Please check file permissions and try again."
            elif "Timeout" in error_type:
                suggestion = (
                    "Consider increasing the timeout or reducing "
                    "the task complexity."
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UAR error",
                    "message": "Request processing failed",
                    "error_type": error_type,
                    "request_id": request_id,
                    "suggestion": suggestion,
                },
            ) from e
        except Exception as e:
            logger.error(
                "[%s] Unexpected error in run_goal: %s",
                request_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": (
                        "An unexpected error occurred while "
                        "processing your request"
                    ),
                    "request_id": request_id,
                    "suggestion": (
                        "Please try again later. If the problem persists, "
                        "contact support with the request ID."
                    ),
                },
            ) from e


@router.get("/api/uar/skills")
async def get_skills():
    """Return list of registered skills to ensure frontend/backend validation
    consistency."""
    from uar.core.registry import registry

    return {"skills": registry.list()}


@router.post("/api/uar/skills/ping")
async def ping_skill(
    body: dict[str, Any],
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Dry-run a skill to verify availability.

    Resolves lazy skills and reports registration status.
    Does not execute the skill payload — only verifies it can be loaded.
    """
    import time

    from uar.core.registry import registry

    rate_limit_middleware(request, credentials)
    auth_middleware(credentials)

    name = body.get("skill", "")
    if not name or not isinstance(name, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_skill", "message": "Provide 'skill'"},
        )

    start = time.perf_counter()
    if name not in registry.list():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "skill_not_found",
                "message": f"Skill '{name}' is not registered",
                "skill": name,
            },
        )
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {"status": "ok", "skill": name, "latency_ms": latency_ms}


@router.get("/api/uar/runs/{run_id}/timeline")
async def get_run_timeline(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return timeline projection for a specific run."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False
    record = store.get_by_run_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Run not found"},
        )
    owner = record.get("user_id") or record.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "Access denied to this run",
            },
        )
    rr = run_record_from_dict(record)
    return timeline_from_record(rr)


@router.get(
    "/api/uar/runs",
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@error_handler_middleware
async def list_runs(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """List all stored runs"""
    from uar.api.server import store

    # Apply rate limiting
    rate_limit_middleware(request, credentials)

    # Get user info
    user_info = auth_middleware(credentials)

    # Log request
    request_id = request_logging_middleware(request, user_info)

    try:
        user_id = user_info.get("user") if user_info else None
        runs = store.list_records(user_id=user_id)
        logger.info(
            "[%s] Listed %s runs for user %s",
            request_id,
            len(runs),
            user_id or "anonymous",
        )
        return runs

    except Exception as e:
        logger.error(
            "[%s] Error listing runs: %s", request_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve runs",
                "request_id": request_id,
            },
        ) from e


@router.get("/api/uar/runs/{run_id}")
async def get_run(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Fetch a full run record by ID (includes events)."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    record = store.get_by_run_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Run not found"},
        )

    owner = record.get("user_id") or record.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    return record


@router.get("/api/uar/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Fetch just the event stream for a run."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    record = store.get_by_run_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Run not found"},
        )

    owner = record.get("user_id") or record.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    events = record.get("events", [])
    return {"run_id": run_id, "events": events}


@router.get("/api/uar/runs/{run_id}/replay")
async def get_run_replay(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return a replay-friendly summary of a historical run."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    record = store.get_by_run_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Run not found"},
        )

    owner = record.get("user_id") or record.get("user", "")
    if owner and owner != user and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    rr = run_record_from_dict(record)
    return replay_summary(rr)


@router.get("/api/provenance/{run_id}")
async def get_provenance(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Fetch provenance data for a specific run.

    Returns the UOR address, witness data, and verification status
    for cryptographic audit of the run.
    """
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else "anonymous"

    # Load from the globally configured store (Json, Sqlite, or Postgres)
    record = store.get_by_run_id(run_id)

    if not record:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify ownership if not admin
    is_admin = user_info.get("tier") == "admin" if user_info else False
    if record.get("user_id") != user and not is_admin:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this run"
        )

    # Build provenance response
    provenance = {
        "run_id": run_id,
        "uor_address": record.get("uor_address"),
        "uor_witness": record.get("uor_witness"),
        "timestamp": record.get("timestamp"),
        "goal": record.get("goal"),
        "skills": record.get("skills", []),
        "verification": {
            "address_present": bool(record.get("uor_address")),
            "witness_present": bool(record.get("uor_witness")),
        },
    }

    return provenance


@router.post("/api/uar/query-code")
async def query_code(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Ask a natural-language question about the codebase via Greptile.

    Requires ``GREPTILE_API_KEY`` env var. Falls back to a mock
    response when not configured so the endpoint is always callable.
    """
    from uar.api.server import _auth_svc

    user = _auth_svc.require_user(credentials)
    question = body.get("question", "")
    if not question or not isinstance(question, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_question",
                "message": "Provide a 'question' string",
            },
        )

    try:
        from uar.integrations import GreptileClient

        client = GreptileClient()
        result = await client.query(
            question,
            repo=body.get("repo"),
            branch=body.get("branch", "main"),
        )
        return {
            "answer": result.get("answer", ""),
            "references": result.get("references", []),
            "repo": body.get("repo") or client.repo,
            "user": user["user"],
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "integration_not_installed",
                "message": "Greptile integration not installed. "
                "Run: pip install 'universal-agent-runtime[greptile]'",
            },
        ) from None
    except Exception as exc:
        logger.exception("Greptile query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "greptile_error",
                "message": "Greptile query failed",
            },
        ) from exc


@router.get("/api/uar/runs/{run_id}/compare/{other_run_id}")
async def compare_runs(
    run_id: str,
    other_run_id: str,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Compare two runs and return a structured diff."""
    from uar.api.server import store

    rate_limit_middleware(request, credentials)
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else "anonymous"
    is_admin = user_info.get("tier") == "admin" if user_info else False

    rec_a = store.get_by_run_id(run_id)
    rec_b = store.get_by_run_id(other_run_id)

    if not rec_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Run {run_id} not found",
            },
        )
    if not rec_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Run {other_run_id} not found",
            },
        )

    # Ownership check
    for rec, rid in [(rec_a, run_id), (rec_b, other_run_id)]:
        owner = rec.get("user_id") or rec.get("user", "")
        if owner and owner != user and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": f"Access denied to run {rid}",
                },
            )

    # Helper: confidence & failure analytics
    def _analyze(record_dict: dict) -> dict:
        try:
            rec = run_record_from_dict(record_dict)
            rc = score_replay(rec)
            conf = rc.to_dict().get("confidence", {})
        except Exception:
            conf = {}
        events = record_dict.get("events") or []
        failures = [
            e for e in events
            if e.get("error") or e.get("type") == "error"
        ]
        skills = record_dict.get("skills") or []
        return {
            "confidence_score": conf.get("score"),
            "confidence_tier": conf.get("tier"),
            "event_count": len(events),
            "failure_count": len(failures),
            "skills": list(skills),
            "status": record_dict.get("status"),
            "goal_id": record_dict.get("goal_id"),
        }

    a = _analyze(rec_a)
    b = _analyze(rec_b)

    # Skill diff
    set_a = set(a["skills"])
    set_b = set(b["skills"])
    skills_added = list(set_b - set_a)
    skills_removed = list(set_a - set_b)

    # Failure skill extraction
    def _failure_skills(record_dict: dict) -> list:
        events = record_dict.get("events") or []
        failed = set()
        for e in events:
            if e.get("error") or e.get("type") == "error":
                skill = e.get("skill")
                if skill:
                    failed.add(skill)
        return list(failed)

    failures_a = _failure_skills(rec_a)
    failures_b = _failure_skills(rec_b)

    # Verdict
    verdict = "equivalent"
    a_score = a["confidence_score"] or 0
    b_score = b["confidence_score"] or 0
    a_fail = a["failure_count"]
    b_fail = b["failure_count"]

    if b_score > a_score and b_fail < a_fail:
        verdict = "improved"
    elif b_score < a_score or b_fail > a_fail:
        verdict = "degraded"
    elif b_score != a_score or b_fail != a_fail:
        verdict = "mixed"

    return {
        "run_a": run_id,
        "run_b": other_run_id,
        "verdict": verdict,
        "status": {"a": a["status"], "b": b["status"]},
        "goal_id": {"a": a["goal_id"], "b": b["goal_id"]},
        "confidence": {
            "a": a["confidence_score"],
            "b": b["confidence_score"],
            "delta": (
                (b["confidence_score"] or 0)
                - (a["confidence_score"] or 0)
            ),
        },
        "events": {
            "a": a["event_count"],
            "b": b["event_count"],
            "delta": b["event_count"] - a["event_count"],
        },
        "failures": {
            "a": a["failure_count"],
            "b": b["failure_count"],
            "delta": b["failure_count"] - a["failure_count"],
        },
        "skills": {
            "a": a["skills"],
            "b": b["skills"],
            "added": skills_added,
            "removed": skills_removed,
        },
        "failure_skills": {
            "a": failures_a,
            "b": failures_b,
        },
    }


@router.post("/api/uar/runs/bulk-delete")
async def bulk_delete_runs(
    body: dict[str, Any],
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Bulk delete runs by a list of run IDs or a time-based filter.

    Body schema:
      { "run_ids": ["r1", "r2"] }
      or
      { "older_than_days": 30 }
    """
    from uar.api.server import store

    rate_limit_middleware(request, credentials)
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else "anonymous"

    run_ids = body.get("run_ids")
    older_than_days = body.get("older_than_days")

    if run_ids is not None:
        if not isinstance(run_ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_run_ids",
                    "message": "Expected list",
                },
            )
        removed = 0
        is_admin = bool(user_info and user_info.get("tier") == "admin")
        errors = []
        for rid in run_ids:
            rec = store.get_by_run_id(rid)
            if rec:
                owner = rec.get("user_id") or rec.get("user", "")
                if owner == user or is_admin:
                    try:
                        store.delete(rid)
                        removed += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to delete run %s: %s", rid, exc
                        )
                        errors.append(str(exc))
        if errors:
            if removed == 0:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "delete_failed",
                        "message": f"All deletions failed: {errors[0]}",
                        "failures": errors,
                    },
                )
            # Partial success: surface the failures so callers know some
            # runs were skipped.
            return {
                "deleted": removed,
                "filter": "run_ids",
                "failed": len(errors),
                "errors": errors[:10],  # cap to avoid huge payloads
            }
        return {"deleted": removed, "filter": "run_ids"}

    if older_than_days is not None:
        try:
            days = int(older_than_days)
            if days < 0:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_older_than_days",
                    "message": "Must be a non-negative integer",
                },
            ) from None
        is_admin = bool(user_info and user_info.get("tier") == "admin")
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Admin access required for time-based purge",
                },
            )
        try:
            removed = store.purge_old_records(days)
        except Exception as exc:
            logger.warning("Purge failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "purge_failed",
                    "message": str(exc),
                },
            ) from exc
        return {"deleted": removed, "filter": f"older_than_{days}_days"}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "missing_filter",
            "message": "Provide 'run_ids' or 'older_than_days'",
        },
    )


@router.get("/api/uar/runs/failure-clusters")
async def get_failure_clusters(
    hours: int = Query(24, ge=1, le=168),
    top: int = Query(10, ge=1, le=50),
    request: Request = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Aggregate failure events from recent runs into clusters.

    Issue #93 — Phase D2.3: Failure Clustering.
    Groups failures by skill and error message, returning the top
    clusters with counts and affected run counts.  No new storage.
    """
    from uar.api.server import store

    rate_limit_middleware(request, credentials)
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    import time
    cutoff = time.time() - (hours * 3600)

    # Fetch all runs and filter by time + ownership
    all_runs = store.list_records(user_id=user if is_admin else user)
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    # Cluster by (skill, error_key)
    skill_clusters: dict[str, dict] = {}
    error_clusters: dict[str, dict] = {}
    total_failures = 0

    for run in recent_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue
        run_id = run.get("run_id") or run.get("id", "")
        events = run.get("events") or []
        for ev in events:
            is_fail = ev.get("error") or ev.get("type") == "error"
            if not is_fail:
                continue
            total_failures += 1
            skill = ev.get("skill", "unknown")
            err_msg = str(ev.get("error", ev.get("message", "unknown")))
            err_key = err_msg[:80]  # truncate for clustering key

            # Skill cluster
            if skill not in skill_clusters:
                skill_clusters[skill] = {
                    "skill": skill,
                    "count": 0,
                    "runs": set(),
                    "latest": 0,
                }
            sc = skill_clusters[skill]
            sc["count"] += 1
            sc["runs"].add(run_id)
            ts = ev.get("timestamp", run.get("created_at", 0))
            if ts > sc["latest"]:
                sc["latest"] = ts
                sc["latest_error"] = err_msg[:120]

            # Error cluster
            if err_key not in error_clusters:
                error_clusters[err_key] = {
                    "error": err_key,
                    "count": 0,
                    "runs": set(),
                    "skills": set(),
                    "latest": 0,
                }
            ec = error_clusters[err_key]
            ec["count"] += 1
            ec["runs"].add(run_id)
            ec["skills"].add(skill)
            if ts > ec["latest"]:
                ec["latest"] = ts

    # Sort and cap
    skill_list = sorted(
        skill_clusters.values(),
        key=lambda x: x["count"],
        reverse=True,
    )[:top]
    error_list = sorted(
        error_clusters.values(),
        key=lambda x: x["count"],
        reverse=True,
    )[:top]

    # Convert sets to counts for JSON serialization
    for item in skill_list:
        item["run_count"] = len(item.pop("runs"))
    for item in error_list:
        item["run_count"] = len(item.pop("runs"))
        item["skill_count"] = len(item.pop("skills"))

    return {
        "hours": hours,
        "total_runs_scanned": len(recent_runs),
        "total_failures": total_failures,
        "top_skills": skill_list,
        "top_errors": error_list,
    }


@router.get("/api/uar/topology/hot-paths")
async def get_topology_hot_paths(
    hours: int = Query(168, ge=1, le=720),
    top: int = Query(15, ge=1, le=50),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Derive execution topology from recent runs.

    Issue #95 — Phase D3.1: Topology Hot Paths.
    Analyzes run records to produce:
    - Node utilization (skill invocations, success rate)
    - Edge utilization (skill-to-skill transitions)
    - Recipe utilization (executions, success rate)
    Zero new storage layer.
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

    import time
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False
    cutoff = time.time() - (hours * 3600)

    all_runs = store.list_records(user_id=user if is_admin else user)
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    recipes: dict[str, dict] = {}

    for run in recent_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue

        status_ok = run.get("status") == "success"
        skills = run.get("skills") or []
        meta = run.get("metadata") or {}
        exec_order = meta.get("execution_order") or []

        # Node counts from skills list
        for skill in skills:
            if skill not in nodes:
                nodes[skill] = {
                    "skill": skill,
                    "invocations": 0,
                    "successes": 0,
                    "failures": 0,
                }
            nodes[skill]["invocations"] += 1
            if status_ok:
                nodes[skill]["successes"] += 1
            else:
                nodes[skill]["failures"] += 1

        # Edge counts from skill sequence
        for i in range(len(skills) - 1):
            src = skills[i]
            dst = skills[i + 1]
            key = f"{src}→{dst}"
            if key not in edges:
                edges[key] = {
                    "source": src,
                    "target": dst,
                    "transitions": 0,
                    "failures": 0,
                }
            edges[key]["transitions"] += 1
            if not status_ok:
                edges[key]["failures"] += 1

        # Recipe counts from execution_order metadata
        for item in exec_order:
            if isinstance(item, dict) and item.get("type") == "recipe":
                rid = item.get("content", item.get("id", "unknown"))
                if rid not in recipes:
                    recipes[rid] = {
                        "recipe": rid,
                        "executions": 0,
                        "successes": 0,
                        "failures": 0,
                    }
                recipes[rid]["executions"] += 1
                if status_ok:
                    recipes[rid]["successes"] += 1
                else:
                    recipes[rid]["failures"] += 1

    # Sort and cap
    node_list = sorted(
        nodes.values(), key=lambda x: x["invocations"], reverse=True
    )[:top]
    edge_list = sorted(
        edges.values(), key=lambda x: x["transitions"], reverse=True
    )[:top]
    recipe_list = sorted(
        recipes.values(), key=lambda x: x["executions"], reverse=True
    )[:top]

    # Compute success rates
    for n in node_list:
        total = n["invocations"]
        n["success_rate"] = round(n["successes"] / total, 2) if total else 0
    for e in edge_list:
        total = e["transitions"]
        e["success_rate"] = round(
            (total - e["failures"]) / total, 2
        ) if total else 0
    for r in recipe_list:
        total = r["executions"]
        r["success_rate"] = round(r["successes"] / total, 2) if total else 0

    return {
        "hours": hours,
        "total_runs": len(recent_runs),
        "nodes": node_list,
        "edges": edge_list,
        "recipes": recipe_list,
    }


@router.get("/api/uar/topology/failure-hotspots")
async def get_failure_hotspots(
    hours: int = Query(168, ge=1, le=720),
    top: int = Query(10, ge=1, le=50),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Overlay failure data onto topology nodes and edges.

    Issue #96 — Phase D3.2: Failure Hotspots.
    Correlates run failures with skill usage and transitions to
    identify the most dangerous nodes and edges.
    Zero new storage layer.
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

    import time
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False
    cutoff = time.time() - (hours * 3600)

    all_runs = store.list_records(user_id=user if is_admin else user)
    recent_runs = [
        r for r in all_runs
        if r.get("created_at", 0) >= cutoff
        or r.get("timestamp", 0) >= cutoff
    ]

    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    total_failures = 0

    for run in recent_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue

        skills = run.get("skills") or []
        events = run.get("events") or []
        run_id = run.get("run_id") or run.get("id", "")

        # Identify failing skills in this run
        failed_skills = set()
        for ev in events:
            if ev.get("error") or ev.get("type") == "error":
                skill = ev.get("skill")
                if skill:
                    failed_skills.add(skill)
        total_failures += len(failed_skills)

        # Node data
        for skill in skills:
            if skill not in nodes:
                nodes[skill] = {
                    "skill": skill,
                    "invocations": 0,
                    "failures": 0,
                    "affected_runs": set(),
                }
            nodes[skill]["invocations"] += 1
            if skill in failed_skills:
                nodes[skill]["failures"] += 1
                nodes[skill]["affected_runs"].add(run_id)

        # Edge data
        for i in range(len(skills) - 1):
            src = skills[i]
            dst = skills[i + 1]
            key = f"{src}→{dst}"
            if key not in edges:
                edges[key] = {
                    "source": src,
                    "target": dst,
                    "transitions": 0,
                    "failures": 0,
                    "affected_runs": set(),
                }
            edges[key]["transitions"] += 1
            if src in failed_skills or dst in failed_skills:
                edges[key]["failures"] += 1
                edges[key]["affected_runs"].add(run_id)

    # Compute severity
    def _severity(failure_rate: float) -> str:
        if failure_rate >= 0.5:
            return "critical"
        if failure_rate >= 0.2:
            return "warning"
        return "healthy"

    node_list = []
    for n in nodes.values():
        inv = n["invocations"]
        fr = n["failures"] / inv if inv else 0
        n["failure_rate"] = round(fr, 2)
        n["severity"] = _severity(fr)
        n["affected_runs"] = len(n.pop("affected_runs"))
        node_list.append(n)

    edge_list = []
    for e in edges.values():
        tr = e["transitions"]
        fr = e["failures"] / tr if tr else 0
        e["failure_rate"] = round(fr, 2)
        e["severity"] = _severity(fr)
        e["affected_runs"] = len(e.pop("affected_runs"))
        edge_list.append(e)

    # Sort by failure rate desc
    node_list = sorted(
        node_list, key=lambda x: x["failure_rate"], reverse=True
    )[:top]
    edge_list = sorted(
        edge_list, key=lambda x: x["failure_rate"], reverse=True
    )[:top]

    return {
        "hours": hours,
        "total_runs": len(recent_runs),
        "total_failures": total_failures,
        "nodes": node_list,
        "edges": edge_list,
    }
