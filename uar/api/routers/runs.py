"""Run execution and query endpoints for the UAR API."""

import logging
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
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

    # Field-level diff
    fields = [
        "status",
        "skills",
        "outputs",
        "events",
        "timeline",
        "metrics",
    ]
    diffs = {}
    for field in fields:
        val_a = rec_a.get(field)
        val_b = rec_b.get(field)
        if val_a != val_b:
            diffs[field] = {"a": val_a, "b": val_b}

    return {
        "run_a": run_id,
        "run_b": other_run_id,
        "same_status": rec_a.get("status") == rec_b.get("status"),
        "same_skills": rec_a.get("skills") == rec_b.get("skills"),
        "diffs": diffs,
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
