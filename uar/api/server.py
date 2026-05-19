import json
import logging
import os
import time
import uuid
import asyncio
from typing import Any, Dict, List, Optional

from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    status,
    Response,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from uar.core.contracts import GoalSpec
from uar.core.exceptions import UARError, ValidationError, PathSecurityError
from uar.core.planner import SimplePlanner
from uar.core.replay import run_record_from_events
from uar.core.orchestrator import build_orchestration_plan
from uar.core.recipes import RECIPE_MAP
from uar.api.advanced_endpoints import router as advanced_router
from uar.core.validation import (
    validate_goal,
    validate_skills,
    validate_input_path,
)
from uar.memory.json_store import JsonRunStore
from .middleware import (
    error_handler_middleware,
    rate_limit_middleware,
    auth_middleware,
    request_logging_middleware,
    build_rate_limit_key,
)
from .tracing import trace_span
from uar.api.metrics import get_metrics_collector

# Constants
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1024 * 64  # 64KB
DEFAULT_BROWSE_LIMIT = 200
BACKPRESSURE_DELAY = 0.1  # seconds
SHUTDOWN_SLEEP = 0.1  # seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _validate_recipe(recipe: Any) -> bool:
    """Validate a single recipe structure. Returns True if valid."""
    if not isinstance(recipe, dict):
        logger.warning(f"Invalid recipe (not a dict): {recipe}")
        return False
    if "id" not in recipe:
        logger.warning(f"Recipe missing 'id' field: {recipe}")
        return False
    if "skills" not in recipe:
        logger.warning(
            f"Recipe '{recipe.get('id')}' missing 'skills' field"
        )
        return False
    if not isinstance(recipe["skills"], list):
        logger.warning(
            f"Recipe '{recipe['id']}' has invalid 'skills' (not a list)"
        )
        return False
    return True


def _validate_recipes(recipes: List[Any]) -> List[Dict[str, Any]]:
    """Validate a list of recipes and return only valid ones."""
    validated_recipes = []
    for recipe in recipes:
        if _validate_recipe(recipe):
            validated_recipes.append(recipe)
    return validated_recipes


# Backpressure configuration
BACKPRESSURE_ENABLED = (
    os.getenv("BACKPRESSURE_ENABLED", "true").lower() == "true"
)
BACKPRESSURE_THRESHOLD = int(
    os.getenv("BACKPRESSURE_THRESHOLD", "100")
)  # Max buffered events

# register skills
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa
import uar.skills.graphrag_skills  # noqa
import uar.skills.autonomi_storage  # noqa
import uar.skills.atomic_lang_model  # noqa
import uar.skills.math_compute  # noqa
import uar.skills.cipher_ops  # noqa
import uar.skills.physics_compute  # noqa
import uar.skills.openai_skills  # noqa
import uar.skills.lm_studio_skills  # noqa
import uar.skills.anthropic_skills  # noqa
import uar.skills.gemini_skills  # noqa
import uar.skills.mistral_skills  # noqa
import uar.skills.groq_skills  # noqa
import uar.skills.huggingface_skills  # noqa
import uar.skills.together_skills  # noqa
import uar.skills.advanced_integrations  # noqa


# Lifespan for graceful startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for graceful startup and shutdown."""
    # Startup
    logger.info("UAR API starting up...")
    # Clean up orphaned temp files on startup
    library = _library_dir()
    _cleanup_orphaned_temp_files(library)
    # Seed UOR standard runtimes (idempotent)
    try:
        from uar.objects import get_default_store, seed_standard_runtimes

        seed_standard_runtimes(get_default_store())
    except Exception as exc:  # noqa: BLE001 - non-fatal at startup
        logger.warning("UOR runtime seeding skipped: %s", exc)
    yield
    # Shutdown - drain in-flight requests
    logger.info(
        "UAR API shutting down, draining requests (5s grace period)..."
    )
    import asyncio

    await asyncio.sleep(SHUTDOWN_SLEEP)  # Let any in-flight requests complete
    logger.info("UAR API shutdown complete")


# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS_ALLOW_CREDENTIALS = (
    os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
)
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "*")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*")

app = FastAPI(
    title="UAR API",
    description="Universal Agent Runtime API with production security "
    "features",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=[CORS_ALLOW_METHODS] if CORS_ALLOW_METHODS != "*" else ["*"],
    allow_headers=[CORS_ALLOW_HEADERS] if CORS_ALLOW_HEADERS != "*" else ["*"],
)

# Include advanced integrations router
app.include_router(advanced_router)

# Include consolidated UOR object/runtime/agent router (formerly
# apps/api-python/main.py).
from uar.api.routers import uor_router  # noqa: E402

app.include_router(uor_router)

store = JsonRunStore()

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


# Custom exception handlers for UAR exceptions
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "Validation error",
                "code": exc.code.value,
                "message": str(exc),
                "field": getattr(exc, "field", None),
            }
        },
    )


@app.exception_handler(PathSecurityError)
async def path_security_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "Path security violation",
                "code": exc.code.value,
                "message": str(exc),
                "field": "input_path",
            }
        },
    )


@app.exception_handler(UARError)
async def uar_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "error": "Internal error",
                "code": exc.code.value,
                "message": str(exc),
            }
        },
    )


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None
    timeout_seconds: Optional[float] = None
    metadata: Optional[dict] = None
    # Support for nested recipe structure
    # Format: [{type: 'skill'|'recipe', content: str, id: str}]
    execution_order: Optional[List[Dict[str, Any]]] = None

    @field_validator("goal")
    @classmethod
    def validate_goal_field(cls, v):
        return validate_goal(v)

    @field_validator("skills")
    @classmethod
    def validate_skills_field(cls, v):
        return validate_skills(v)

    @field_validator("input_path")
    @classmethod
    def validate_input_path_field(cls, v):
        from pathlib import Path
        import os

        root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        return validate_input_path(v, allowed_root=root)

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_field(cls, v):
        if v is not None:
            from uar.core.validation import validate_timeout

            return validate_timeout(v)
        return v

    @field_validator("execution_order")
    @classmethod
    def validate_execution_order_field(cls, v):
        """Validate execution_order structure and content."""
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError("execution_order must be an array")

        seen_ids = set()
        for i, item in enumerate(v):
            # Check required fields
            if not isinstance(item, dict):
                raise ValueError(
                    f"execution_order[{i}] must be an object"
                )
            if "type" not in item:
                raise ValueError(
                    f"execution_order[{i}] missing required field: type"
                )
            if "content" not in item:
                raise ValueError(
                    f"execution_order[{i}] missing required field: content"
                )
            if "id" not in item:
                raise ValueError(
                    f"execution_order[{i}] missing required field: id"
                )

            # Validate type
            if item["type"] not in ["skill", "recipe"]:
                raise ValueError(
                    f"execution_order[{i}] has invalid type: "
                    f"{item['type']}. Must be 'skill' or 'recipe'"
                )

            # Check for duplicate IDs
            if item["id"] in seen_ids:
                raise ValueError(
                    f"execution_order[{i}] has duplicate ID: {item['id']}"
                )
            seen_ids.add(item["id"])

            # Validate content based on type
            if item["type"] == "recipe":
                if item["content"] not in RECIPE_MAP:
                    raise ValueError(
                        f"execution_order[{i}] references unknown "
                        f"recipe: {item['content']}. "
                        f"Available: {list(RECIPE_MAP.keys())}"
                    )
            elif item["type"] == "skill":
                # Import here to avoid circular dependency
                from uar.core.registry import registry
                if not registry.is_registered(item["content"]):
                    raise ValueError(
                        f"execution_order[{i}] references unknown "
                        f"skill: {item['content']}. "
                        f"Available skills: {registry.list()}"
                    )

        return v


class RunResponse(BaseModel):
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List
    status: str
    errors: List[str]
    events: List[dict]
    final_context: dict


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    field: Optional[str] = None


def _build_goal(req: RunRequest) -> GoalSpec:
    """Build GoalSpec with proper validation and unique ID"""
    goal_id = f"api-{uuid.uuid4().hex[:8]}"

    metadata: dict[str, Any] = {}
    if req.input_path:
        metadata["input_path"] = req.input_path
    if req.timeout_seconds:
        metadata["timeout_seconds"] = req.timeout_seconds
    if req.metadata:
        # User-supplied extras (e.g. graphrag_method, ollama_model)
        # Protected keys (input_path, timeout_seconds, execution_order) cannot
        # be overridden by user-provided metadata. Other user-provided metadata
        # keys will override any defaults with the same name.
        extras = {
            k: v
            for k, v in req.metadata.items()
            if k not in {"input_path", "timeout_seconds", "execution_order"}
        }
        metadata.update(extras)

    # Handle execution_order with nested recipe structure
    # Note: Recipe expansion is handled by the executor in
    # _expand_execution_order() to ensure a single source of truth.
    # We only store the execution_order here.
    skills = req.skills or []
    if req.execution_order:
        # Store the execution order in metadata for the executor
        metadata["execution_order"] = req.execution_order
        # For backward compatibility with old clients that don't use
        # execution_order, if skills is empty but execution_order is
        # provided, we don't expand here. The executor will handle
        # expansion from execution_order. If both are provided,
        # execution_order takes precedence.
        if not skills:
            # Empty skills list - executor will expand from execution_order
            skills = []

    return GoalSpec(
        id=goal_id,
        user_intent=req.goal,
        objective=req.goal,
        required_skills=skills,
        metadata=metadata,
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Dependency to get current authenticated user"""
    return auth_middleware(credentials)


@app.post(
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
    with trace_span("api.run_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting
        rate_limit_middleware(request, credentials)

        # Get user info
        user_info = auth_middleware(credentials)

        # Log request
        request_id = request_logging_middleware(request, user_info)

        try:
            goal = _build_goal(req)
            planner = SimplePlanner()
            strategy = planner.plan(goal)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            result = executor.run(strategy, goal, timeout_seconds=timeout)

            store.append(result)
            logger.info(
                f"[{request_id}] Run completed successfully: {result.run_id}"
            )

            return result

        except ValidationError as e:
            logger.warning(f"[{request_id}] Validation error: {str(e)}")
            # Provide user-friendly error messages based on field
            user_message = str(e)
            if e.field == "goal":
                user_message = (
                    f"Invalid goal: {str(e)}. "
                    "Please provide a clear goal description "
                    "(3-10,000 characters)."
                )
            elif e.field == "skills":
                user_message = (
                    f"Invalid skills: {str(e)}. "
                    "Please check that the skills are available "
                    "in the system."
                )
            elif e.field == "input_path":
                user_message = (
                    f"Invalid input path: {str(e)}. "
                    "Please provide a valid path within the "
                    "project directory."
                )
            elif e.field == "timeout_seconds":
                user_message = (
                    f"Invalid timeout: {str(e)}. "
                    "Please provide a timeout between 1 and "
                    "300 seconds."
                )
            elif e.field == "execution_order":
                user_message = (
                    f"Invalid execution order: {str(e)}. "
                    "Please check that all skills and recipes are valid."
                )

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
            )
        except UARError as e:
            logger.error(f"[{request_id}] UAR error: {str(e)}")
            # Provide more context for UARError types
            error_type = type(e).__name__
            suggestion = "Please check your request and try again."
            if "Path" in error_type:
                suggestion = (
                    "Please verify the file path exists and "
                    "is accessible."
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
                    "message": str(e),
                    "error_type": error_type,
                    "request_id": request_id,
                    "suggestion": suggestion,
                },
            )
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
            )


@app.websocket("/api/uar/stream/ws")
async def stream_goal_ws(
    websocket: WebSocket,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Execute a goal and stream events via WebSocket for real-time updates"""
    request_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    # Accept WebSocket immediately - rate limiting is applied after
    # receiving the request body to allow skill-specific limits
    await websocket.accept()
    websocket.state.correlation_id = correlation_id

    try:
        # Receive the run request from WebSocket with timeout
        # to prevent malicious clients from holding connections open
        # indefinitely
        websocket_timeout = int(
            os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30")
        )
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=websocket_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[{request_id}] WebSocket receive timeout after "
                f"{websocket_timeout}s"
            )
            await websocket.send_json({
                "type": "error",
                "error": "Receive timeout",
                "message": (
                    f"No data received within {websocket_timeout} seconds"
                ),
                "request_id": request_id,
                "code": "RECEIVE_TIMEOUT"
            })
            await websocket.close()
            return

        # Validate request size before parsing
        # Use same limit as HTTP endpoints (10MB)
        from uar.api.middleware import DEFAULT_MAX_REQUEST_BODY_BYTES
        max_body_size = int(
            os.getenv(
                "MAX_REQUEST_BODY_BYTES",
                str(DEFAULT_MAX_REQUEST_BODY_BYTES)
            )
        )
        json_size = len(json.dumps(data))
        if json_size > max_body_size:
            logger.warning(
                f"WebSocket request too large: {json_size} bytes > "
                f"{max_body_size}"
            )
            await websocket.send_json({
                "type": "error",
                "error": "Request body too large",
                "message": f"Maximum body size is {max_body_size} bytes",
                "request_id": request_id,
                "code": "BODY_TOO_LARGE"
            })
            await websocket.close()
            return

        try:
            req = RunRequest(**data)
        except ValidationError as e:
            await websocket.send_json({
                "type": "error",
                "error": "Validation error",
                "message": str(e),
                "request_id": request_id,
                "code": "VALIDATION_ERROR"
            })
            await websocket.close()
            return

        # Apply rate limiting with skill extraction
        from uar.api.middleware import (
            _extract_skill_from_request_data,
            check_rate_limit,
            rate_limiter,
        )

        # Generate rate limit key using shared function
        client_ip = (
            websocket.client.host if websocket.client else "unknown"
        )
        rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)

        # Extract first skill for skill-specific rate limiting
        skill_name = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )

        # Check for skill-specific rate limits
        limit, window, rate_limit_type = check_rate_limit(
            rate_limit_key, tier, skill_name
        )

        try:
            allowed, remaining = rate_limiter.is_allowed(
                rate_limit_key, limit, window
            )
        except Exception as rate_limit_error:
            logger.error(
                f"[{request_id}] Rate limit check failed: "
                f"{str(rate_limit_error)}"
            )
            await websocket.send_json({
                "type": "error",
                "error": "Rate limit check failed",
                "message": "Internal error checking rate limit",
                "request_id": request_id,
                "code": "RATE_LIMIT_ERROR",
            })
            try:
                await websocket.close(code=4000, reason="Rate limit error")
            except Exception:
                pass
            return

        if not allowed:
            logger.warning(
                f"WebSocket rate limit exceeded for {rate_limit_key}"
            )
            await websocket.send_json({
                "type": "error",
                "error": "Rate limit exceeded",
                "message": (
                    f"{limit} requests per {window} seconds allowed."
                ),
                "request_id": request_id,
                "code": "RATE_LIMIT_EXCEEDED",
                "skill": skill_name if skill_name else None,
            })
            # Use proper WebSocket close code 4000 (application error)
            # Note: WebSocket close codes are limited to 0-999, 4000-4999
            # 4000-4099 is reserved for application-specific codes
            try:
                await websocket.close(code=4000, reason="Rate limit exceeded")
            except Exception as close_error:
                # If close fails, try without code
                logger.warning(
                    f"[{request_id}] WebSocket close with code failed: "
                    f"{str(close_error)}"
                )
                try:
                    await websocket.close()
                except Exception as fallback_error:
                    logger.error(
                        f"[{request_id}] WebSocket close fallback failed: "
                        f"{str(fallback_error)}"
                    )
            return

        # Get user info
        user_info = auth_middleware(credentials)

        # Log request (request_id generated at line 556)
        user_str = user_info['user'] if user_info else 'anonymous'
        logger.info(
            f"[{request_id}] WebSocket request from {user_str}"
        )

        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            cid = getattr(websocket.state, "correlation_id", "")

            def create_event(
                event_type: str,
                run_id: str,
                skill=None,
                payload=None,
                error=None,
            ):
                """Create a properly formatted event."""
                return {
                    "schema_version": "uar.event.v1",
                    "type": event_type,
                    "run_id": run_id,
                    "goal_id": strategy.goal_id,
                    "skill": skill,
                    "timestamp": time.time(),
                    "correlation_id": cid,
                    "payload": payload or {},
                    "error": error,
                }

            # Execute and stream events
            events = []
            persisted = False
            try:
                for event in executor.iter_events(
                    strategy, goal, timeout_seconds=timeout, correlation_id=cid
                ):
                    events.append(event)
                    await websocket.send_json(event)

                    # Persist to store on completion
                    if event.get("type") == "complete":
                        try:
                            record = run_record_from_events(
                                events, strategy.ordered_skills
                            )
                            store.append(record)
                            persisted = True
                            logger.info(
                                f"[{request_id}] WebSocket stream completed "
                                f"and persisted: {record.run_id}"
                            )
                        except Exception as persist_error:
                            logger.error(
                                f"[{request_id}] Failed to persist WebSocket "
                                f"stream: {str(persist_error)}"
                            )
            except Exception as exec_error:
                logger.error(
                    f"[{request_id}] Error during executor.iter_events: "
                    f"{str(exec_error)}",
                    exc_info=True
                )
                # Send error event to client
                await websocket.send_json({
                    "type": "error",
                    "error": str(exec_error),
                    "error_type": type(exec_error).__name__,
                    "request_id": request_id
                })
                raise

            # Ensure persistence even if client disconnects
            if events and not persisted:
                try:
                    record = run_record_from_events(
                        events, strategy.ordered_skills
                    )
                    store.append(record)
                    logger.info(
                        f"[{request_id}] WebSocket stream persisted in "
                        f"finally: {record.run_id}"
                    )
                except Exception:
                    pass

        except ValidationError as e:
            await websocket.send_json({
                "type": "error",
                "error": str(e),
                "error_type": "ValidationError",
                "request_id": request_id
            })
        except Exception as e:
            logger.error(
                f"[{request_id}] WebSocket error: {str(e)}",
                extra={
                    "request_id": request_id,
                    "client_host": (
                        websocket.client.host
                        if websocket.client
                        else "unknown"
                    ),
                    "authenticated": credentials is not None,
                }
            )
            await websocket.send_json({
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__,
                "request_id": request_id
            })

    except WebSocketDisconnect:
        logger.info(f"[{request_id}] WebSocket disconnected")
    except Exception as e:
        logger.error(
            f"[{request_id}] WebSocket connection error: {str(e)}",
            extra={
                "request_id": request_id,
                "client_host": (
                    websocket.client.host
                    if websocket.client
                    else "unknown"
                ),
                "authenticated": credentials is not None,
            }
        )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/api/uar/skills")
async def get_skills():
    """Return list of registered skills to ensure frontend/backend validation
    consistency."""
    from uar.core.registry import registry

    return {"skills": registry.list()}


@app.post(
    "/api/uar/stream",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@error_handler_middleware
async def stream_goal(
    req: RunRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Execute a goal and stream events in real-time"""
    with trace_span("api.stream_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting
        rate_limit_middleware(request, credentials)

        # Get user info
        user_info = auth_middleware(credentials)

        # Log request
        request_id = request_logging_middleware(request, user_info)

        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)

            plan = build_orchestration_plan(strategy)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            cid = getattr(request.state, "correlation_id", "")

            def emit(event: dict) -> str:
                return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

            def create_event(
                event_type: str,
                run_id: str,
                skill=None,
                payload=None,
                error=None,
            ):
                """Create a properly formatted event following the
                uar.event.v1 schema.
                """
                return {
                    "schema_version": "uar.event.v1",
                    "type": event_type,
                    "run_id": run_id,
                    "goal_id": strategy.goal_id,
                    "skill": skill,
                    "timestamp": time.time(),
                    "correlation_id": cid,
                    "payload": payload or {},
                    "error": error,
                }

            async def generate():
                events = []
                persisted = False
                last_heartbeat = time.time()
                heartbeat_interval = 30  # Send heartbeat every 30 seconds

                try:
                    # emit orchestration graph first
                    yield emit(
                        create_event(
                            "orchestration_plan",
                            run_id="pending",
                            payload={"graph": plan.to_graph()},
                        )
                    )

                    for event in executor.iter_events(
                        strategy,
                        goal,
                        timeout_seconds=timeout,
                        correlation_id=cid,
                    ):
                        # Check if heartbeat needed
                        current_time = time.time()
                        if current_time - last_heartbeat > heartbeat_interval:
                            yield emit(
                                create_event(
                                    "heartbeat",
                                    run_id="pending",
                                    payload={"timestamp": current_time},
                                )
                            )
                            last_heartbeat = current_time

                        events.append(event)

                        # Backpressure: slow down if too many events buffered
                        if (
                            BACKPRESSURE_ENABLED
                            and len(events) > BACKPRESSURE_THRESHOLD
                        ):
                            logger.debug(
                                f"Backpressure triggered: {len(events)} "
                                f"events buffered, "
                                f"delaying {BACKPRESSURE_DELAY}s"
                            )
                            await asyncio.sleep(BACKPRESSURE_DELAY)

                        yield emit(event)

                    # Persist successful run
                    try:
                        record = run_record_from_events(
                            events, strategy.ordered_skills
                        )
                        store.append(record)
                        persisted = True
                        logger.info(
                            f"[{request_id}] Stream completed and "
                            f"persisted: {record.run_id}"
                        )
                    except Exception as persist_error:
                        logger.error(
                            f"[{request_id}] Failed to persist stream "
                            f"results: {str(persist_error)}"
                        )
                        # Only mark as persisted for deterministic errors
                        # (e.g. EventContractError). Transient I/O errors
                        # should allow retry in finally block.
                        from uar.core.exceptions import EventContractError

                        if isinstance(persist_error, EventContractError):
                            persisted = True
                        # Emit error event to notify client of persistence
                        # failure but don't re-raise - let stream complete
                        yield emit(
                            create_event(
                                "error",
                                run_id="unknown",
                                error=(
                                    f"Execution completed but "
                                    f"persistence failed: {str(persist_error)}"
                                ),
                            )
                        )
                        # Don't re-raise - allow stream to complete

                except Exception as e:
                    logger.error(
                        f"[{request_id}] Stream error: {str(e)}",
                        exc_info=True,
                    )
                    # Emit error event to client (correlation_id included
                    # via create_event)
                    yield emit(
                        create_event("error", run_id="unknown", error=str(e))
                    )
                finally:
                    # Ensure persistence even if client disconnects or
                    # error occurred
                    if events and not persisted:
                        try:
                            record = run_record_from_events(
                                events, strategy.ordered_skills
                            )
                            store.append(record)
                            logger.info(
                                f"[{request_id}] Stream persisted "
                                f"{len(events)} events (fallback)"
                            )
                        except Exception as e:
                            logger.error(
                                f"[{request_id}] Failed to persist stream "
                                f"events in finally: {str(e)}"
                            )

            return StreamingResponse(
                generate(), media_type="text/event-stream"
            )

        except ValidationError as e:
            logger.warning(f"[{request_id}] Stream validation error: {str(e)}")
            # Provide user-friendly error messages based on field
            user_message = str(e)
            if e.field == "goal":
                user_message = (
                    f"Invalid goal: {str(e)}. "
                    "Please provide a clear goal description "
                    "(3-10,000 characters)."
                )
            elif e.field == "skills":
                user_message = (
                    f"Invalid skills: {str(e)}. "
                    "Please check that the skills are available "
                    "in the system."
                )
            elif e.field == "input_path":
                user_message = (
                    f"Invalid input path: {str(e)}. "
                    "Please provide a valid path within the "
                    "project directory."
                )
            elif e.field == "timeout_seconds":
                user_message = (
                    f"Invalid timeout: {str(e)}. "
                    "Please provide a timeout between 1 and "
                    "300 seconds."
                )
            elif e.field == "execution_order":
                user_message = (
                    f"Invalid execution order: {str(e)}. "
                    "Please check that all skills and recipes are valid."
                )

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
            )
        except UARError as e:
            logger.error(f"[{request_id}] Stream UAR error: {str(e)}")
            # Provide more context for UARError types
            error_type = type(e).__name__
            suggestion = "Please check your request and try again."
            if "Path" in error_type:
                suggestion = (
                    "Please verify the file path exists and "
                    "is accessible."
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
                    "message": str(e),
                    "error_type": error_type,
                    "request_id": request_id,
                    "suggestion": suggestion,
                },
            )
        except Exception as e:
            logger.error(
                f"[{request_id}] Unexpected stream error: {str(e)}",
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
            )


@app.get(
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
    # Apply rate limiting
    rate_limit_middleware(request, credentials)

    # Get user info
    user_info = auth_middleware(credentials)

    # Log request
    request_id = request_logging_middleware(request, user_info)

    try:
        runs = store.list_records()
        logger.info(f"[{request_id}] Listed {len(runs)} runs")
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
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint (backwards-compatible alias for liveness)."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/health/live")
async def liveness_probe():
    """Kubernetes liveness probe — process is alive."""
    return {"status": "alive"}


@app.get("/api/metrics")
async def metrics_endpoint():
    """Prometheus-compatible metrics endpoint."""
    metrics = get_metrics_collector()
    return Response(
        content=metrics.get_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/metrics/json")
async def metrics_json_endpoint():
    """JSON metrics endpoint for debugging."""
    metrics = get_metrics_collector()
    return metrics.get_metrics()


@app.get("/api/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe — service is ready to accept traffic."""
    checks = {}

    # Check skills loaded
    from uar.core.registry import registry

    skills = registry.list()
    checks["skills_loaded"] = len(skills) > 0

    # Check disk writable
    try:
        test_file = store.runs_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        checks["disk_writable"] = True
    except Exception:
        checks["disk_writable"] = False

    # Check Ollama reachable (non-blocking, best-effort)
    try:
        import httpx

        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        r = httpx.get(f"{ollama_host.rstrip('/')}/api/tags", timeout=2.0)
        checks["ollama_reachable"] = r.is_success
    except Exception:
        checks["ollama_reachable"] = False

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
        },
    )


def _docs_root():
    from pathlib import Path
    import os

    return Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()


def _library_dir():
    """Default ingest library: <PROJECT_ROOT>/.uar_library (overridable)."""
    from pathlib import Path
    import os

    custom = os.getenv("UAR_LIBRARY_DIR")
    if custom:
        p = Path(custom).resolve()
    else:
        p = _docs_root() / ".uar_library"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cleanup_orphaned_temp_files(library) -> int:
    """Clean up orphaned .tmp files in the library directory.

    Returns the number of files cleaned up.
    """
    import time

    cleaned = 0
    current_time = time.time()
    # Clean temp files older than 1 hour
    max_age_seconds = 3600

    for tmp_file in library.glob("*.tmp"):
        try:
            # Check file age
            file_age = current_time - tmp_file.stat().st_mtime
            if file_age > max_age_seconds:
                tmp_file.unlink()
                cleaned += 1
                logger.info(f"Cleaned up orphaned temp file: {tmp_file.name}")
        except (OSError, PermissionError):
            # Skip files that can't be accessed
            pass

    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} orphaned temp file(s)")
    return cleaned


# Upload limits
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
MAX_UPLOAD_BYTES = int(
    os.getenv("UAR_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
)  # 50MB
ALLOWED_UPLOAD_EXTS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".xlsm",
    ".ipynb",
    ".parquet",
    ".feather",
    ".txt",
    ".md",
    ".rst",
    ".tex",
    ".bib",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".htm",
    ".xml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".r",
    ".jl",
    ".rmd",
    ".qmd",
}


def _resolve_docs_path(raw: str):
    """Resolve a user-provided path (relative or absolute) and require it be
    contained within PROJECT_ROOT. Raises PathSecurityError otherwise."""
    from pathlib import Path

    root = _docs_root()
    raw = (raw or "").strip()
    if not raw:
        raise ValidationError("Empty path", field="path")
    if "\x00" in raw:
        raise PathSecurityError(raw, "Path contains null bytes")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathSecurityError(
            str(resolved), f"Path is outside PROJECT_ROOT ({root})"
        )
    return resolved


@app.get(
    "/api/uar/docs/presets",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
)
async def docs_presets():
    """Return convenient preset document paths inside PROJECT_ROOT."""
    project_root = _docs_root()
    library = _library_dir()
    candidates = ["docs", "specs", "tests", "apps/web/src", "uar"]
    presets = [{"name": "📚 library", "path": str(library)}]
    for name in candidates:
        p = project_root / name
        if p.exists() and p.is_dir():
            presets.append({"name": name, "path": str(p)})
    return {
        "project_root": str(project_root),
        "library": str(library),
        "presets": presets,
    }


@app.post(
    "/api/uar/docs/upload",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def docs_upload(files: List[UploadFile] = File(...)):
    """
    Upload one or more files into the default library directory.
    Filenames are sanitized; duplicates get a numeric suffix.
    """
    from pathlib import Path

    request_id = str(uuid.uuid4())
    library = _library_dir()
    saved = []
    rejected = []

    for upload in files:
        original = upload.filename or "upload.bin"
        # Sanitize: keep only the basename, strip null bytes / path separators
        safe_name = Path(original).name.replace("\x00", "")
        if not safe_name or safe_name in (".", ".."):
            rejected.append({"name": original, "reason": "invalid filename"})
            continue
        ext = Path(safe_name).suffix.lower()
        if ext and ext not in ALLOWED_UPLOAD_EXTS:
            rejected.append(
                {"name": safe_name, "reason": f"extension not allowed: {ext}"}
            )
            continue

        # Resolve dest with collision-free unique naming
        # (UUID-based with retry)
        # Use retry loop to handle race conditions from concurrent uploads
        dest = library / safe_name
        max_attempts = 5
        for attempt in range(max_attempts):
            if not dest.exists():
                # Try atomic file creation with exclusive access
                try:
                    import os
                    fd = os.open(
                        dest,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o644,
                    )
                    # Successfully created exclusively - close fd properly
                    # Use os.fdopen to wrap in file object for proper cleanup
                    try:
                        with os.fdopen(fd, "wb") as _:
                            pass  # Just create empty file as placeholder
                    except OSError:
                        # If fdopen or close fails, try to unlink the file
                        try:
                            os.close(fd)  # Ensure fd is closed first
                        except OSError:
                            pass
                        try:
                            dest.unlink()
                        except OSError:
                            pass
                        raise
                    break
                except FileExistsError:
                    # Race condition - another process created it
                    pass
            # File exists or race occurred, generate unique name
            stem = Path(safe_name).stem
            unique_id = str(uuid.uuid4())[:8]
            dest = library / f"{stem}.{unique_id}{ext}"
        else:
            # Max attempts reached - reject this upload
            rejected.append(
                {
                    "name": safe_name,
                    "reason": "Could not generate unique filename",
                }
            )
            continue

        # Stream-copy with size cap using temp file for atomic rename
        size = 0
        temp_dest = dest.with_suffix(dest.suffix + ".tmp")
        try:
            with open(temp_dest, "wb") as out:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        rejected.append(
                            {
                                "name": safe_name,
                                "reason": (
                                    f"file too large "
                                    f"(>{MAX_UPLOAD_BYTES} bytes)"
                                ),
                            }
                        )
                        size = -1
                        break
                    out.write(chunk)
        except Exception as e:
            logger.exception(f"[{request_id}] upload failed for {safe_name}")
            try:
                temp_dest.unlink()
            except OSError:
                pass
            rejected.append({"name": safe_name, "reason": str(e)})
            continue
        finally:
            await upload.close()

        # Atomic rename from temp to final destination
        if size >= 0:
            try:
                temp_dest.rename(dest)
                saved.append(
                    {
                        "name": dest.name,
                        "path": str(dest),
                        "size": size,
                        "ext": ext,
                    }
                )
            except OSError as e:
                logger.exception(
                    f"[{request_id}] rename failed for {safe_name}"
                )
                try:
                    temp_dest.unlink()
                except OSError:
                    pass
                rejected.append(
                    {"name": safe_name, "reason": f"Rename failed: {e}"}
                )
        else:
            # File too large - clean up temp file
            try:
                temp_dest.unlink()
            except OSError:
                pass

    return {
        "library": str(library),
        "saved": saved,
        "rejected": rejected,
        "request_id": request_id,
    }


@app.get("/api/uar/docs/library")
async def docs_library():
    """List files in the default ingest library."""
    library = _library_dir()
    entries = []
    total = 0
    for p in sorted(library.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        st = p.stat()
        total += st.st_size
        entries.append(
            {
                "name": p.name,
                "path": str(p),
                "size": st.st_size,
                "ext": p.suffix.lower(),
                "mtime": st.st_mtime,
            }
        )
    return {
        "library": str(library),
        "count": len(entries),
        "total_bytes": total,
        "entries": entries,
    }


@app.delete("/api/uar/docs/library")
async def docs_library_delete(name: str):
    """Delete a single file from the library by its basename."""
    from pathlib import Path

    library = _library_dir()
    safe_name = Path(name).name
    if not safe_name or safe_name in (".", ".."):
        return JSONResponse(
            status_code=400, content={"error": "Invalid name", "message": name}
        )
    target = (library / safe_name).resolve()
    try:
        target.relative_to(library)
    except ValueError:
        return JSONResponse(
            status_code=400, content={"error": "Invalid name", "message": name}
        )
    if not target.exists() or not target.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "message": str(target)},
        )
    try:
        target.unlink()
    except OSError as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Delete failed", "message": str(e)},
        )
    return {"deleted": str(target)}


@app.get(
    "/api/uar/docs/browse",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def docs_browse(
    path: str, limit: int = DEFAULT_BROWSE_LIMIT, recursive: bool = False
):
    """
    Directory/file browser. When recursive=false (default), lists the
    immediate children of a directory (navigable). When recursive=true,
    lists all files under the path (doc_ingest preview).
    """
    request_id = str(uuid.uuid4())
    try:
        p = _resolve_docs_path(path)
        safe_path = str(p)
        if not p.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Path not found",
                    "message": safe_path,
                    "request_id": request_id,
                },
            )
        entries = []
        total_bytes = 0
        truncated = False
        parent = str(p.parent) if p.parent != p else None
        if p.is_file():
            st = p.stat()
            entries.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "size": st.st_size,
                    "ext": p.suffix.lower(),
                    "is_dir": False,
                }
            )
            total_bytes += st.st_size
        else:
            iterator = p.rglob("*") if recursive else p.iterdir()
            count = 0
            for entry in iterator:
                if count >= limit:
                    truncated = True
                    break
                try:
                    is_dir = entry.is_dir()
                    st = entry.stat()
                    entries.append(
                        {
                            "name": entry.name,
                            "path": str(entry),
                            "size": 0 if is_dir else st.st_size,
                            "ext": "" if is_dir else entry.suffix.lower(),
                            "is_dir": is_dir,
                        }
                    )
                    if not is_dir:
                        total_bytes += st.st_size
                    count += 1
                except OSError:
                    continue
            # Sort: dirs first, then name
            entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        by_ext: dict = {}
        for e in entries:
            if not e["is_dir"]:
                by_ext[e["ext"] or "(none)"] = (
                    by_ext.get(e["ext"] or "(none)", 0) + 1
                )
        return {
            "path": safe_path,
            "parent": parent,
            "is_dir": p.is_dir(),
            "recursive": recursive,
            "file_count": sum(1 for e in entries if not e["is_dir"]),
            "dir_count": sum(1 for e in entries if e["is_dir"]),
            "total_bytes": total_bytes,
            "truncated": truncated,
            "by_extension": by_ext,
            "entries": entries,
        }
    except (ValidationError, PathSecurityError) as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid path",
                "message": str(e),
                "request_id": request_id,
            },
        )
    except Exception as e:
        logger.exception(f"[{request_id}] docs_browse failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
                "request_id": request_id,
            },
        )


@app.post(
    "/api/uar/docs/create_folder",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Folder already exists"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def docs_create_folder(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """
    Create a new folder in the docs directory.
    Expects JSON body with 'path' (parent directory) and 'name' (folder name).
    """
    request_id = str(uuid.uuid4())
    auth_middleware(credentials)  # Auth check, result unused
    try:
        body = await request.json()
        parent_path = body.get("path")
        folder_name = body.get("name")

        # Validate input types
        if (
            not isinstance(parent_path, str)
            or not isinstance(folder_name, str)
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid input types",
                    "message": "Both 'path' and 'name' must be strings",
                    "request_id": request_id,
                },
            )

        # Check required fields
        if not parent_path or not folder_name:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Missing required fields",
                    "message": "Both 'path' and 'name' are required",
                    "request_id": request_id,
                },
            )

        # Trim whitespace
        folder_name = folder_name.strip()
        if not folder_name:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid folder name",
                    "message": (
                        "Folder name cannot be empty or "
                        "whitespace only"
                    ),
                    "request_id": request_id,
                },
            )

        # Prevent path traversal and invalid characters in folder name
        if (
            "/" in folder_name
            or "\\" in folder_name
            or ".." in folder_name
            or "\x00" in folder_name
            or any(ord(c) < 32 for c in folder_name)
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid folder name",
                    "message": (
                        "Folder name cannot contain slashes, "
                        "parent directory references, null "
                        "bytes, or control characters"
                    ),
                    "request_id": request_id,
                },
            )

        # Check for reserved Windows names
        reserved_names = {"CON", "PRN", "AUX", "NUL"}
        reserved_names.update(f"COM{i}" for i in range(1, 10))
        reserved_names.update(f"LPT{i}" for i in range(1, 10))
        if folder_name.upper() in reserved_names:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid folder name",
                    "message": f"'{folder_name}' is a reserved system name",
                    "request_id": request_id,
                },
            )

        # Check length limits (most filesystems limit to 255 chars)
        if len(folder_name) > 255:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid folder name",
                    "message": (
                        "Folder name exceeds maximum "
                        "length of 255 characters"
                    ),
                    "request_id": request_id,
                },
            )

        # Prevent names starting/ending with dot (hidden files on Unix)
        if folder_name.startswith(".") or folder_name.endswith("."):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid folder name",
                    "message": "Folder name cannot start or end with a dot",
                    "request_id": request_id,
                },
            )

        # Resolve and validate parent path
        parent = _resolve_docs_path(parent_path)
        if not parent.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Parent directory not found",
                    "message": str(parent),
                    "request_id": request_id,
                },
            )

        if not parent.is_dir():
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Parent is not a directory",
                    "message": str(parent),
                    "request_id": request_id,
                },
            )

        # Create the new folder
        new_folder = parent / folder_name
        try:
            new_folder.mkdir(parents=False, exist_ok=False)
            logger.info(f"[{request_id}] Created folder: {new_folder}")
        except FileExistsError:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Folder already exists",
                    "message": str(new_folder),
                    "request_id": request_id,
                },
            )

        return {
            "path": str(new_folder),
            "message": "Folder created successfully",
            "request_id": request_id,
        }

    except (ValidationError, PathSecurityError) as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid path",
                "message": str(e),
                "request_id": request_id,
            },
        )
    except Exception as e:
        logger.exception(f"[{request_id}] docs_create_folder failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
                "request_id": request_id,
            },
        )


@app.get("/api/status")
async def get_status(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Get system status and user info"""
    user_info = auth_middleware(credentials)

    return {
        "status": "operational",
        "user": user_info,
        "available_skills": [
            "section_sum",
            "doc_ingest",
            "dependency_map",
            "sum_review",
            "ollama_generate",
            "graphrag_init",
            "graphrag_index",
            "graphrag_query",
            "autonomi_upload",
            "autonomi_download",
            "autonomi_status",
            "alm_analyze",
            "alm_generate",
            "alm_verify",
            "cipher_ops",
            "math_compute",
            "physics_compute",
            "openai_chat",
            "openai_completion",
            "openai_embedding",
            "lm_studio_chat",
            "lm_studio_completion",
            "lm_studio_embedding",
            "anthropic_chat",
            "anthropic_completion",
            "anthropic_embedding",
            "gemini_chat",
            "gemini_completion",
            "gemini_embedding",
            "mistral_chat",
            "mistral_completion",
            "mistral_embedding",
            "groq_chat",
            "groq_completion",
            "groq_embedding",
            "huggingface_chat",
            "huggingface_completion",
            "huggingface_embedding",
            "together_chat",
            "together_completion",
            "together_embedding",
        ],
    }
