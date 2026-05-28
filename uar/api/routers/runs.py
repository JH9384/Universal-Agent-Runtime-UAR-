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
                        f"[{request_id}] Idempotency hit: "
                        f"{req.idempotency_key}"
                    )
                    return cached

            goal = _build_goal(req)
            planner = SimplePlanner()
            strategy = planner.plan(goal)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            result = executor.run(strategy, goal, timeout_seconds=timeout)
            result.user_id = user_info["user"] if user_info else None

            # Cache result for idempotency
            if req.idempotency_key:
                _idempotency_set(req.idempotency_key, result)

            store.append(result)
            logger.info(
                f"[{request_id}] Run completed successfully: {result.run_id}"
            )

            return result

        except ValidationError as e:
            logger.warning("[%s] Validation error: %s", request_id, e)
            if e.field == "goal":
                user_message = (
                    "Invalid goal. Please provide a clear goal "
                    "description (3-10,000 characters)."
                )
            elif e.field == "skills":
                user_message = (
                    "Invalid skills. Please check that the skills "
                    "are available in the system."
                )
            elif e.field == "input_path":
                user_message = (
                    "Invalid input path. Please provide a valid "
                    "path within the project directory."
                )
            elif e.field == "timeout_seconds":
                user_message = (
                    "Invalid timeout. Please provide a timeout "
                    "between 1 and 300 seconds."
                )
            elif e.field == "execution_order":
                user_message = (
                    "Invalid execution order. Please check that "
                    "all skills and recipes are valid."
                )
            else:
                user_message = "Invalid input provided"

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Validation error",
                    "message": user_message,
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
                f"[{request_id}] Unexpected error in run_goal: {str(e)}",
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


@router.get("/api/uar/runs/{run_id}/timeline")
async def get_run_timeline(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return timeline projection for a specific run."""
    from uar.api.server import store

    user_info = auth_middleware(credentials)
    user_id = user_info["user"] if user_info else None
    records = store.list_records(user_id=user_id)
    for rec in records:
        if rec.get("run_id") == run_id:
            rr = run_record_from_dict(rec)
            return timeline_from_record(rr)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "message": "Run not found"},
    )


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
        user_id = user_info["user"] if user_info else None
        runs = store.list_records(user_id=user_id)
        logger.info(
            f"[{request_id}] Listed {len(runs)} runs "
            f"for user {user_id or 'anonymous'}"
        )
        return runs

    except Exception as e:
        logger.error(
            f"[{request_id}] Error listing runs: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve runs",
                "request_id": request_id,
            },
        ) from e


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
    user = user_info["user"] if user_info else "anonymous"

    # Load from the globally configured store (Json, Sqlite, or Postgres)
    record = store.get_by_run_id(run_id)

    if not record:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify ownership if not admin
    if record.get("user_id") != user and user != "admin":
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
