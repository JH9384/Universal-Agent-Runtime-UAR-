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
from starlette.websockets import WebSocketState
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import (
    BaseModel,
    field_validator,
    ValidationError as PydanticValidationError,
)

from uar.core.contracts import GoalSpec
from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version
from uar.core.binary_stream import (
    serialize_trefoil,
    serialize_molecular,
    serialize_quantum_circuit,
)
from uar.core.exceptions import UARError, ValidationError, PathSecurityError
from uar.core.planner import SimplePlanner
from uar.core.recipes import DEFAULT_RECIPES
from uar.core.timeline import timeline_from_record
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
    rate_limiter,
    RATE_LIMITS,
    apply_middleware,
    _extract_skill_from_request_data,
)
from .tracing import trace_span
from uar.api.metrics import get_metrics_collector
from uar.services import (
    AuthService,
    RecipeService,
    EventService,
    GoalExecutionService,
)

# Optional OpenTelemetry tracing (no-op if not installed)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    _tracing_available = True
except ImportError:
    _tracing_available = False

    class _NoOpTracer:
        """Fallback tracer when OpenTelemetry is not installed."""

        def start_as_current_span(self, name, **_kwargs):
            class _NoOpContextManager:
                def __enter__(self):
                    return self

                def __exit__(self, *_exc):
                    pass

            return _NoOpContextManager()

    trace = _NoOpTracer()


def _setup_tracing(app: FastAPI) -> None:
    """Initialize OpenTelemetry tracing if enabled and available."""
    if not _tracing_available:
        return
    if os.getenv("UAR_ENABLE_TRACING", "").lower() != "true":
        return

    provider = TracerProvider()
    # Console exporter for local dev; OTLP for production
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter()
        except ImportError:
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor().instrument_app(app)
    logger.info("OpenTelemetry tracing initialized")


# Constants
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB

# SSE connection limit
_MAX_CONCURRENT_SSE_PER_IP = int(os.getenv("UAR_MAX_SSE_PER_IP", "5"))
_sse_connections: Dict[str, int] = {}
_sse_connections_lock = asyncio.Lock()

# Idempotency key cache: key -> result (no TTL eviction for simplicity)
_idempotency_cache: Dict[str, Any] = {}
_IDEMPOTENCY_TTL = int(os.getenv("UAR_IDEMPOTENCY_TTL", "86400"))  # 24h


class _WebSocketConnectionCounter:
    """Global WebSocket connection cap with async-safe acquire/release.

    Also updates the metrics collector so active connections are visible
    in Prometheus / JSON metrics.
    """

    def __init__(self, max_connections: int = 0):
        self.max_connections = max_connections
        self.count = 0
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        if self.max_connections <= 0:
            from uar.api.metrics import get_metrics_collector

            get_metrics_collector().record_connection(+1)
            self.count += 1
            return True
        async with self.lock:
            if self.count >= self.max_connections:
                return False
            self.count += 1
            from uar.api.metrics import get_metrics_collector

            get_metrics_collector().record_connection(+1)
            return True

    def release(self) -> None:
        if self.count > 0:
            self.count = max(0, self.count - 1)
            from uar.api.metrics import get_metrics_collector

            get_metrics_collector().record_connection(-1)


_ws_conn_counter = _WebSocketConnectionCounter(
    int(os.getenv("WEBSOCKET_MAX_CONNECTIONS", "0"))
)
CHUNK_SIZE = 1024 * 64  # 64KB
DEFAULT_BROWSE_LIMIT = 200
BACKPRESSURE_DELAY = 0.1  # seconds
SHUTDOWN_SLEEP = float(
    os.getenv("SHUTDOWN_GRACE_SECONDS", "30")
)  # seconds to drain active requests

# WebSocket robustness
WS_HEARTBEAT_INTERVAL = 20.0  # seconds
WS_HEARTBEAT_TIMEOUT = 60.0  # seconds without pong before disconnect
WS_BATCH_SIZE = 10  # max events per WebSocket send batch
WS_BATCH_TIMEOUT = 0.05  # seconds to wait before flushing partial batch

# Streaming bounds
MAX_STREAM_EVENTS = 5000
# ^ hard cap on events per run to prevent memory exhaustion
EVENT_BUFFER_SIZE = 200
# ^ ring buffer size for SSE persistence

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.info(
    "Booting UAR %s (aligned with UOR %s)",
    get_uar_version(),
    get_uor_version(),
)


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
import uar.skills.uor_ecosystem_skills  # noqa
import uar.skills.trefoil_simulation  # noqa
import uar.skills.molecular_visualization  # noqa
import uar.skills.quantum_circuit_visualization  # noqa
import uar.skills.riscv_sim  # noqa
import uar.skills.verilog_parse  # noqa
import uar.skills.fpga_verify  # noqa
import uar.skills.myhdl_design  # noqa
import uar.skills.riscv_cycle  # noqa
import uar.skills.verilator_sim  # noqa
import uar.skills.micropython  # noqa
import uar.skills.platformio  # noqa
import uar.skills.stub_skills  # noqa
import uar.skills.data_viz_3d  # noqa
import uar.skills.doc_ingest_enhanced  # noqa
import uar.skills.stem_extended  # noqa
import uar.skills.cv_skills  # noqa
import uar.skills.ml_tools  # noqa

# Validate canonical recipe skill references now that all skills are
# registered in the global registry.
from uar.core.recipes import validate_recipes  # noqa

validate_recipes()


async def _retention_purge_loop() -> None:
    """Background task: purge old run records periodically."""
    from uar.memory.json_store import JsonRunStore
    from uar.config import config

    if config.run_retention_days <= 0:
        return

    import asyncio

    store = JsonRunStore()
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour
            removed = store.purge_old_records(config.run_retention_days)
            if removed > 0:
                logger.info(
                    f"Purged {removed} run records older than "
                    f"{config.run_retention_days} days"
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Retention purge failed: %s", exc)


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

    # Load external skill plugins (~/.uar/skills/ and PyPI entry points)
    try:
        from uar.skills.plugin import load_plugins

        load_plugins()
    except Exception as exc:  # noqa: BLE001 - non-fatal at startup
        logger.warning("Plugin loading skipped: %s", exc)

    # Initialize optional OpenTelemetry tracing
    _setup_tracing(app)

    # Start background data retention purge task
    purge_task = None
    from uar.config import config

    if config.run_retention_days > 0:
        import asyncio

        purge_task = asyncio.create_task(_retention_purge_loop())

    yield
    # Shutdown - drain in-flight requests and WebSocket connections
    if purge_task is not None:
        purge_task.cancel()
        try:
            await purge_task
        except asyncio.CancelledError:
            pass
    logger.info(
        "UAR API shutting down, draining active connections "
        f"({SHUTDOWN_SLEEP}s grace period)..."
    )
    import asyncio

    start_shutdown = time.time()
    while time.time() - start_shutdown < SHUTDOWN_SLEEP:
        ws_active = _ws_conn_counter.count
        if ws_active == 0:
            logger.info("All connections drained cleanly")
            break
        logger.info(
            f"Waiting for {ws_active} active WebSocket(s) to close..."
        )
        await asyncio.sleep(1.0)
    else:
        logger.warning(
            f"Shutdown grace period expired with "
            f"{_ws_conn_counter.count} active connection(s) remaining"
        )
    logger.info("UAR API shutdown complete")


# CORS configuration
# In production, CORS_ORIGINS must be explicitly set. Defaulting to an empty
# list blocks all cross-origin requests unless explicitly allowed.
_is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
_default_cors = "" if _is_production else "http://localhost:3000"
CORS_ORIGINS = [
    o
    for o in os.getenv("CORS_ORIGINS", _default_cors).split(",")
    if o
]
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

# Apply request logging, body parsing, and size-limit middleware
apply_middleware(app)

# Response compression for large JSON/SSE payloads
app.add_middleware(
    GZipMiddleware,
    minimum_size=int(os.getenv("UAR_GZIP_MIN_SIZE", "1024")),
)

# Universal request-timing middleware (records every HTTP endpoint)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    from uar.api.metrics import get_metrics_collector

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - start
        get_metrics_collector().record_request(
            request.url.path, duration, error=True
        )
        raise
    duration = time.perf_counter() - start
    get_metrics_collector().record_request(
        request.url.path,
        duration,
        error=response.status_code >= 500,
    )
    # Log slow requests (> 5 s = p99 threshold for POST /api/uar/run)
    SLOW_REQUEST_THRESHOLD = 5.0  # seconds
    if duration > SLOW_REQUEST_THRESHOLD:
        logger.warning(
            "slow_request path=%s duration=%.3fs status=%s "
            "correlation_id=%s",
            request.url.path,
            duration,
            getattr(response, "status_code", "unknown"),
            request.headers.get("x-correlation-id", "none"),
        )
    return response

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict[str, Any]:
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
    request.state.user_id = user_info["user"]
    return user_info


# Include advanced integrations router
app.include_router(advanced_router, dependencies=[Depends(require_auth)])

# Include consolidated UOR object/runtime/agent router (formerly
# apps/api-python/main.py).
from uar.api.routers import uor_router  # noqa: E402

app.include_router(uor_router, dependencies=[Depends(require_auth)])

# Auto-select run store backend
if os.getenv("UAR_DATABASE_URL"):
    from uar.memory.postgres_store import PostgresRunStore
    store = PostgresRunStore()
else:
    store = JsonRunStore()

_uar_start_time = time.time()


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
    # Opt-in to hierarchical recipe execution (discrete units with
    # snapshot/retry/params scoping) instead of legacy flat expansion.
    use_hierarchical: Optional[bool] = None
    # Idempotency key for safe retries (cached 24h)
    idempotency_key: Optional[str] = None

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
                raise ValueError(f"execution_order[{i}] must be an object")
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

            # Note: Content validation (recipe exists, skill registered)
            # is deferred to _build_goal() where metadata-provided
            # recipe_definitions can be merged with canonical recipes.
            if item["type"] == "recipe":
                if not isinstance(item["content"], str) or not item["content"]:
                    raise ValueError(
                        f"execution_order[{i}] recipe content must be a "
                        f"non-empty string"
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
    error_code: Optional[str] = None
    message: Optional[str] = None
    detail: Optional[str] = None
    field: Optional[str] = None
    request_id: Optional[str] = None


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

    # Build merged recipe map from canonical + user-provided definitions
    # so user-created recipes sent in metadata are valid for execution.
    recipe_definitions = metadata.pop("recipe_definitions", [])
    merged_recipes: dict[str, dict[str, Any]] = dict(DEFAULT_RECIPES)
    for recipe in recipe_definitions:
        if (
            isinstance(recipe, dict)
            and "id" in recipe
            and "skills" in recipe
            and isinstance(recipe["skills"], list)
        ):
            merged_recipes[recipe["id"]] = recipe

    # Validate execution_order recipe content against merged map
    if req.execution_order:
        for i, item in enumerate(req.execution_order):
            if item.get("type") == "recipe":
                content = item.get("content")
                if content not in merged_recipes:
                    raise ValidationError(
                        f"execution_order[{i}] references unknown "
                        f"recipe: {content}. "
                        f"Available: {list(merged_recipes.keys())}",
                        field="execution_order",
                    )

    # Handle execution_order with nested recipe structure
    # Note: Recipe expansion is handled by the executor in
    # _expand_execution_order() to ensure a single source of truth.
    # We only store the execution_order here.
    skills = req.skills or []
    if req.execution_order:
        # Store the execution order in metadata for the executor
        metadata["execution_order"] = req.execution_order
        # Pass merged recipe definitions so the executor can expand
        # user-created recipes as well as canonical ones.
        metadata["recipe_definitions"] = list(merged_recipes.values())
        # For backward compatibility with old clients that don't use
        # execution_order, if skills is empty but execution_order is
        # provided, we don't expand here. The executor will handle
        # expansion from execution_order. If both are provided,
        # execution_order takes precedence.
        if not skills:
            # Empty skills list - executor will expand from execution_order
            skills = []

    if req.use_hierarchical is not None:
        metadata["use_hierarchical"] = req.use_hierarchical

    return GoalSpec(
        id=goal_id,
        user_intent=req.goal,
        objective=req.goal,
        required_skills=skills,
        metadata=metadata,
    )


async def _stream_binary_visualization(
    websocket: WebSocket,
    event: Dict[str, Any],
) -> None:
    """Send binary simulation data after a skill_complete JSON event.

    Detects visualization skills and streams their 3D data as
    binary WebSocket frames for efficient client rendering.
    """
    skill = event.get("skill")
    payload = event.get("payload", {})
    result = payload.get("result", {})

    serializers = {
        "trefoil_simulation": serialize_trefoil,
        "molecular_visualization": serialize_molecular,
        "quantum_circuit_visualization": serialize_quantum_circuit,
    }

    serializer = serializers.get(skill)
    if not serializer:
        return

    try:
        chunks = serializer(result)
        for name, data in chunks.items():
            await websocket.send_bytes(
                name.encode("utf-8") + b"\x00" + data
            )
    except Exception:
        # Binary streaming is best-effort; JSON event already sent
        pass


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
                cached = _idempotency_cache.get(req.idempotency_key)
                if cached:
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
                _idempotency_cache[req.idempotency_key] = result

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
):
    """Execute a goal and stream events via WebSocket for real-time updates"""
    request_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    # Parse Authorization header first so we can rate-limit before
    # accepting the connection and consuming server resources.
    auth_header = websocket.headers.get("authorization", "")
    credentials: Optional[HTTPAuthorizationCredentials] = None
    if auth_header.lower().startswith("bearer "):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=auth_header[7:],
        )

    # Apply connection-level rate limiting BEFORE accepting the
    # WebSocket, to prevent connection-exhaustion attacks.
    client_ip = websocket.client.host if websocket.client else "unknown"
    rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
    limit = RATE_LIMITS.get(tier, RATE_LIMITS["default"])["requests"]
    window = RATE_LIMITS.get(tier, RATE_LIMITS["default"])["window"]
    allowed, _ = rate_limiter.is_allowed(rate_limit_key, limit, window)
    if not allowed:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return

    # Enforce global WebSocket connection cap
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return

    try:
        await websocket.accept()
    except Exception:
        _ws_conn_counter.release()
        raise

    websocket.state.correlation_id = correlation_id

    _goal_id = ""

    def create_event(
        event_type: str,
        run_id: str,
        skill=None,
        payload=None,
        error=None,
    ):
        return _event_svc.create(
            event_type=event_type,
            run_id=run_id,
            goal_id=_goal_id,
            skill=skill,
            payload=payload,
            error=error,
            correlation_id=correlation_id,
        )

    try:
        # Receive the run request from WebSocket with timeout
        # to prevent malicious clients from holding connections open
        # indefinitely
        websocket_timeout = int(os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30"))
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(), timeout=websocket_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[{request_id}] WebSocket receive timeout after "
                f"{websocket_timeout}s"
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": (
                            f"No data received within {websocket_timeout} "
                            f"seconds"
                        ),
                        "request_id": request_id,
                        "code": "RECEIVE_TIMEOUT",
                    },
                )
            )
            await websocket.close()
            return

        # Validate request size before parsing
        # Use same limit as HTTP endpoints (10MB)
        from uar.api.middleware import DEFAULT_MAX_REQUEST_BODY_BYTES

        max_body_size = int(
            os.getenv(
                "MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES)
            )
        )
        json_size = len(json.dumps(data))
        if json_size > max_body_size:
            logger.warning(
                f"WebSocket request too large: {json_size} bytes > "
                f"{max_body_size}"
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Request body too large",
                    payload={
                        "message": (
                            f"Maximum body size is {max_body_size} bytes"
                        ),
                        "request_id": request_id,
                        "code": "BODY_TOO_LARGE",
                    },
                )
            )
            await websocket.close()
            return

        try:
            req = RunRequest(**data)
        except ValidationError as e:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": str(e),
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return
        except PydanticValidationError as e:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": str(e),
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return

        # Apply rate limiting with skill extraction
        from uar.api.middleware import check_rate_limit

        # Generate rate limit key using shared function
        client_ip = websocket.client.host if websocket.client else "unknown"
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
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Rate limit check failed",
                    payload={
                        "message": "Internal error checking rate limit",
                        "request_id": request_id,
                        "code": "RATE_LIMIT_ERROR",
                    },
                )
            )
            try:
                await websocket.close(code=1008, reason="Rate limit error")
            except Exception:
                pass
            return

        if not allowed:
            logger.warning(
                f"WebSocket rate limit exceeded for {rate_limit_key}"
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Rate limit exceeded",
                    payload={
                        "message": (
                            f"{limit} requests per {window} seconds allowed."
                        ),
                        "request_id": request_id,
                        "code": "RATE_LIMIT_EXCEEDED",
                        "skill": skill_name if skill_name else None,
                    },
                )
            )
            # Use standard WebSocket close code 1008 (policy violation)
            try:
                await websocket.close(code=1008, reason="Rate limit exceeded")
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
        user_str = user_info["user"] if user_info else "anonymous"
        logger.info(f"[{request_id}] WebSocket request from {user_str}")

        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)
            _goal_id = strategy.goal_id

            # WebSocket heartbeat with coalescing
            last_hb = time.time()
            hb_interval = float(
                os.getenv("UAR_WS_HEARTBEAT_INTERVAL", "30")
            )
            async for event in _exec_svc.stream_goal(
                goal, request_id, user_str, correlation_id,
                yield_persisted=True,
            ):
                await websocket.send_json(event)
                last_hb = time.time()

                # Stream binary visualization data for 3D skills
                if event.get("type") == "skill_complete":
                    try:
                        await _stream_binary_visualization(
                            websocket, event
                        )
                    except Exception:
                        pass

                # Coalesced heartbeat: only emit if idle > interval
                now = time.time()
                if now - last_hb >= hb_interval:
                    await websocket.send_json(
                        _event_svc.heartbeat(
                            run_id="pending",
                            goal_id=_goal_id,
                            correlation_id=correlation_id,
                        )
                    )
                    last_hb = now

        except ValidationError as e:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(e),
                    "error_type": "ValidationError",
                    "request_id": request_id,
                }
            )
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
                },
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_id": request_id,
                }
            )

    except WebSocketDisconnect:
        logger.info(f"[{request_id}] WebSocket disconnected")
    except Exception as e:
        logger.error(
            f"[{request_id}] WebSocket connection error: {str(e)}",
            extra={
                "request_id": request_id,
                "client_host": (
                    websocket.client.host if websocket.client else "unknown"
                ),
                "authenticated": credentials is not None,
            },
        )
    finally:
        _ws_conn_counter.release()
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


@app.get("/api/uar/runs/{run_id}/timeline")
async def get_run_timeline(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return timeline projection for a specific run."""
    user_info = auth_middleware(credentials)
    user_id = user_info["user"] if user_info else None
    records = store.list_records(user_id=user_id)
    for rec in records:
        if rec.get("run_id") == run_id:
            from uar.core.contracts import RunRecord

            rr = RunRecord(**rec)
            return timeline_from_record(rr)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "message": f"Run '{run_id}' not found"},
    )


# Service instances (stateless, safe to share across requests)
_recipe_svc = RecipeService()
_auth_svc = AuthService()
_event_svc = EventService()
_exec_svc = GoalExecutionService(
    event_service=_event_svc,
    store=store,
    max_stream_events=MAX_STREAM_EVENTS,
    event_buffer_size=EVENT_BUFFER_SIZE,
)


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
                "message": msg,
            },
        )
    if "skills must be" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_skills", "message": msg},
        )
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Recipe '{recipe_id}' not found",
            },
        )
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Not owner"},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": "internal", "message": msg},
    )


@app.get("/api/uar/recipes")
async def get_recipes(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return canonical + user-created recipe definitions."""
    user_info = _auth_svc.authenticate(credentials)
    recipes = _recipe_svc.list_all(
        user_id=user_info["user"] if user_info else None
    )
    return {"recipes": recipes}


@app.post("/api/uar/recipes")
async def create_recipe(
    recipe: dict[str, Any],
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


@app.put("/api/uar/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    recipe: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Update an existing user recipe."""
    user = _auth_svc.require_user(credentials)
    try:
        _recipe_svc.update(recipe_id, recipe, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id) from exc
    return {"updated": recipe_id}


@app.delete("/api/uar/recipes/{recipe_id}")
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
        # Apply rate limiting (pass parsed skill to avoid ASGI stream reuse)
        first_skill = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )
        rate_limit_middleware(request, credentials, first_skill=first_skill)

        # Get user info
        user_info = auth_middleware(credentials)
        user_id = user_info["user"] if user_info else None

        # Log request
        request_id = request_logging_middleware(request, user_info)

        client_ip = request.client.host if request.client else "unknown"
        async with _sse_connections_lock:
            current_conns = _sse_connections.get(client_ip, 0)
            if current_conns >= _MAX_CONCURRENT_SSE_PER_IP:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": (
                            "Too many concurrent streaming connections from "
                            f"IP {client_ip} "
                            f"(limit: {_MAX_CONCURRENT_SSE_PER_IP})"
                        ),
                    },
                )
            _sse_connections[client_ip] = current_conns + 1

        async def _release_sse_connection() -> None:
            async with _sse_connections_lock:
                if client_ip in _sse_connections:
                    _sse_connections[client_ip] = max(
                        0, _sse_connections[client_ip] - 1
                    )
                    if _sse_connections[client_ip] == 0:
                        _sse_connections.pop(client_ip, None)

        try:
            goal = _build_goal(req)
            cid = getattr(request.state, "correlation_id", "")

            _sse_emit = _event_svc.emit_sse

            async def _generate():
                try:
                    last_hb = time.time()
                    hb_interval = 30
                    stream = _exec_svc.stream_goal(
                        goal, request_id, user_id, cid
                    )
                    while True:
                        elapsed = time.time() - last_hb
                        timeout = max(0.1, hb_interval - elapsed)
                        try:
                            event = await asyncio.wait_for(
                                stream.__anext__(), timeout=timeout
                            )
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError:
                            now = time.time()
                            if now - last_hb >= hb_interval:
                                yield _sse_emit(
                                    _event_svc.heartbeat(
                                        run_id="pending",
                                        goal_id="",
                                        correlation_id=cid,
                                    )
                                )
                                last_hb = now
                            continue

                        if await request.is_disconnected():
                            break
                        yield _sse_emit(event)
                        last_hb = time.time()
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Stream error: {e}",
                        exc_info=True,
                    )
                    yield _sse_emit(
                        _event_svc.error(
                            run_id="unknown",
                            error_msg=str(e),
                            request_id=request_id,
                            goal_id="",
                            correlation_id=cid,
                        )
                    )
                finally:
                    await _release_sse_connection()

            return StreamingResponse(
                _generate(), media_type="text/event-stream"
            )

        except ValidationError as e:
            await _release_sse_connection()
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
            await _release_sse_connection()
            logger.error(f"[{request_id}] Stream UAR error: {str(e)}")
            # Provide more context for UARError types
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
                    "message": str(e),
                    "error_type": error_type,
                    "request_id": request_id,
                    "suggestion": suggestion,
                },
            )
        except Exception as e:
            await _release_sse_connection()
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


@app.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    """Execute a goal and stream events via WebSocket.

    Includes heartbeat/ping-pong, batching, bounded buffers,
    and graceful error handling.
    """
    request_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    _goal_id = ""

    def create_event(
        event_type: str,
        run_id: str,
        skill=None,
        payload=None,
        error=None,
    ):
        return _event_svc.create(
            event_type=event_type,
            run_id=run_id,
            goal_id=_goal_id,
            skill=skill,
            payload=payload,
            error=error,
            correlation_id=correlation_id,
        )

    # Enforce global WebSocket connection cap
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return

    try:
        await websocket.accept()
    except Exception:
        _ws_conn_counter.release()
        raise

    heartbeat_task = None
    heartbeat_stop = asyncio.Event()
    try:
        # Parse Authorization header manually because HTTPBearer
        # depends on a Request object which is unavailable for
        # WebSocket connections in FastAPI/TestClient.
        auth_header = websocket.headers.get("authorization", "")
        credentials: Optional[HTTPAuthorizationCredentials] = None
        if auth_header.lower().startswith("bearer "):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header[7:],
            )

        # Browser WebSocket cannot send custom headers, so also accept
        # token via query parameter (e.g. /ws/run?token=...).
        if credentials is None:
            token = websocket.query_params.get("token")
            if token:
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials=token,
                )

        # Get user info for ownership tracking
        user_info = auth_middleware(credentials)
        user_str = user_info["user"] if user_info else None

        # Apply rate limiting
        client_ip = websocket.client.host if websocket.client else "unknown"
        rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
        allowed, _ = rate_limiter.is_allowed(
            rate_limit_key,
            RATE_LIMITS.get(tier, RATE_LIMITS["default"])["requests"],
            RATE_LIMITS.get(tier, RATE_LIMITS["default"])["window"],
        )
        if not allowed:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Rate limit exceeded",
                    payload={
                        "request_id": request_id,
                    },
                )
            )
            await websocket.close(code=1008)
            return

        websocket_timeout = int(os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30"))
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=websocket_timeout,
            )
        except asyncio.TimeoutError:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": (
                            f"No data received within {websocket_timeout}s"
                        ),
                        "request_id": request_id,
                    },
                )
            )
            await websocket.close()
            return
        try:
            req = RunRequest(**data)
        except PydanticValidationError as e:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": str(e),
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return
        goal = _build_goal(req)
        strategy = SimplePlanner().plan(goal)
        _goal_id = strategy.goal_id

        # Heartbeat: keep connection alive and detect stale clients
        heartbeat_stop = asyncio.Event()

        async def _heartbeat():
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.wait_for(
                        heartbeat_stop.wait(),
                        timeout=WS_HEARTBEAT_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    pass
                if heartbeat_stop.is_set():
                    break
                try:
                    await websocket.send_json(
                        create_event(
                            "heartbeat",
                            run_id="pending",
                            payload={"timestamp": time.time()},
                        )
                    )
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(_heartbeat())

        batch: list[dict] = []
        batch_deadline: float | None = None

        async def _flush_batch() -> None:
            nonlocal batch, batch_deadline
            if batch:
                for ev in batch:
                    try:
                        await websocket.send_json(ev)
                    except Exception:
                        pass
                    # Stream binary visualization data for 3D skills
                    if ev.get("type") == "skill_complete":
                        try:
                            await _stream_binary_visualization(
                                websocket, ev
                            )
                        except Exception:
                            pass
                batch = []
                batch_deadline = None

        try:
            async for event in _exec_svc.stream_goal(
                goal, request_id, user_str, correlation_id,
                yield_persisted=True,
            ):
                batch.append(event)
                if batch_deadline is None:
                    batch_deadline = time.time() + WS_BATCH_TIMEOUT
                if len(batch) >= WS_BATCH_SIZE:
                    await _flush_batch()
                elif time.time() >= batch_deadline:
                    await _flush_batch()
                # Terminal events must reach client immediately
                if event.get("type") in ("complete", "error"):
                    await _flush_batch()
        finally:
            await _flush_batch()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json({"type": "error", "error": str(e)})
            except Exception:
                pass
    finally:
        _ws_conn_counter.release()
        heartbeat_stop.set()
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        try:
            await websocket.close()
        except Exception:
            pass


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
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint (backwards-compatible alias for liveness)."""
    return {
        "status": "healthy",
        "version": get_uar_version(),
        "uor_upstream_version": get_uor_version(),
    }


@app.get("/api/status")
async def status_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Operational status with skill inventory and authenticated user."""
    user_info = auth_middleware(credentials)
    user = user_info["user"] if user_info else "anonymous"
    from uar.core.registry import registry

    return {
        "status": "operational",
        "available_skills": registry.list(),
        "user": user,
    }


@app.get("/api/health/live")
async def liveness_probe():
    """Kubernetes liveness probe — process is alive."""
    return {"status": "alive"}


@app.get("/api/metrics")
async def metrics_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Prometheus-compatible metrics endpoint.

    Optionally protected by METRICS_API_KEY env var in production.
    """
    _check_metrics_auth(credentials)
    metrics = get_metrics_collector()
    return Response(
        content=metrics.get_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/metrics/json")
async def metrics_json_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """JSON metrics endpoint for debugging.

    Optionally protected by METRICS_API_KEY env var in production.
    """
    _check_metrics_auth(credentials)
    metrics = get_metrics_collector()
    return metrics.get_metrics()


def _check_metrics_auth(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> None:
    """Require Bearer token if METRICS_API_KEY is configured."""
    expected = os.getenv("METRICS_API_KEY", "").strip()
    if not expected:
        return
    token = (
        credentials.credentials
        if credentials and credentials.scheme == "Bearer"
        else ""
    )
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized",
                "message": "Valid metrics API key required",
            },
        )


@app.get("/api/health/circuit-breakers")
async def health_circuit_breakers(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
    """Circuit breaker status for all external services."""
    from uar.core.circuit_breaker_decorator import (
        get_circuit_breaker_states,
        _circuit_breakers,
    )

    states = get_circuit_breaker_states()
    details = {}
    any_open = False
    for name, cb in _circuit_breakers.items():
        state = states.get(name, "unknown")
        if state == "open":
            any_open = True
        details[name] = {
            "state": state,
            "failure_threshold": cb.failure_threshold,
            "recovery_timeout": cb.recovery_timeout,
            "failures": cb._failures,
            "pending_calls": cb._pending_calls,
        }

    status_code = 200 if not any_open else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if not any_open else "degraded",
            "circuits": details,
        },
    )


@app.get("/api/health/dashboard")
async def health_dashboard():
    """Comprehensive health dashboard data for the web UI."""
    from uar.core.registry import registry
    from uar.core.circuit_breaker_decorator import (
        get_circuit_breaker_states,
        _circuit_breakers,
    )

    # Skill availability
    skill_health = []
    for name in registry.list():
        try:
            registry.get(name)
            skill_health.append({"name": name, "available": True})
        except Exception as exc:
            skill_health.append({
                "name": name,
                "available": False,
                "last_error": str(exc)[:100],
            })

    # Circuit breaker states
    cb_states = get_circuit_breaker_states()
    circuit_breakers = []
    for name, cb in _circuit_breakers.items():
        circuit_breakers.append({
            "name": name,
            "state": cb_states.get(name, "unknown"),
            "failures": cb._failures,
            "threshold": cb.failure_threshold,
        })

    return {
        "skills": skill_health,
        "circuit_breakers": circuit_breakers,
        "recent_errors": [],
        "server_version": "1.1.0",
        "uptime_seconds": int(time.time() - _uar_start_time),
    }


@app.get("/api/cache/stats")
async def cache_stats_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return skill cache statistics."""
    from uar.core.skill_cache import get_skill_cache

    cache = get_skill_cache()
    if cache is None:
        return {
            "hits": 0,
            "misses": 0,
            "size": 0,
            "capacity": 0,
        }
    return cache.stats()


@app.post("/api/cache/invalidate")
async def cache_invalidate_endpoint(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Invalidate cache entries.  Omit 'skill' to clear all."""
    from uar.core.skill_cache import get_skill_cache

    cache = get_skill_cache()
    skill = body.get("skill")
    count = cache.invalidate(skill)
    return {"invalidated": count, "skill": skill}


@app.get("/api/sandbox/health")
async def sandbox_health_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return WASM sandbox health."""
    from uar.core.sandbox import WASMSandbox

    return WASMSandbox().health()


@app.post("/api/sandbox/eval")
async def sandbox_eval_endpoint(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Safely evaluate an arithmetic expression in the WASM sandbox."""
    from uar.core.sandbox import sandbox_eval

    expression = body.get("expression", "")
    try:
        result = sandbox_eval(expression)
        return {"status": "completed", "result": result}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "failed", "error": str(exc)},
        )


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
        test_file = store.path.parent / ".health_check"
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

    # Check Redis connectivity (if configured)
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            import redis as _redis

            r = _redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            checks["redis_reachable"] = True
        except Exception:
            checks["redis_reachable"] = False
    else:
        checks["redis_reachable"] = None  # not configured

    # Check circuit breaker states (non-blocking, informational)
    try:
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker_states,
        )

        cb_states = get_circuit_breaker_states()
        open_circuits = [
            name for name, state in cb_states.items() if state == "open"
        ]
        checks["circuit_breakers"] = len(open_circuits) == 0
        checks["open_circuits"] = open_circuits
    except Exception:
        checks["circuit_breakers"] = True
        checks["open_circuits"] = []

    all_ready = all(v for k, v in checks.items() if isinstance(v, bool))
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
        },
    )


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint for scraping.

    Exposes uar_requests_total, uar_errors_total,
    uar_request_duration_seconds histogram (by endpoint),
    and uar_skill_duration_seconds histogram (by skill).
    """
    collector = get_metrics_collector()
    body = collector.get_prometheus_format()
    return Response(content=body, media_type="text/plain")


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
async def docs_presets(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return convenient preset document paths inside PROJECT_ROOT."""
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
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
async def docs_upload(
    files: List[UploadFile] = File(...),
    overwrite: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Upload files to the document library."""
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
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
            for p in (temp_dest, dest):
                try:
                    p.unlink()
                except OSError:
                    pass
            rejected.append({"name": safe_name, "reason": str(e)})
            continue
        finally:
            await upload.close()

        # Atomic rename from temp to final destination
        if size >= 0:
            try:
                # Remove placeholder so rename works on Windows
                if dest.exists():
                    dest.unlink()
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
            # File too large - clean up temp and placeholder
            for p in (temp_dest, dest):
                try:
                    p.unlink()
                except OSError:
                    pass

    return {
        "library": str(library),
        "saved": saved,
        "rejected": rejected,
        "request_id": request_id,
    }


@app.get("/api/uar/docs/library")
async def docs_library_list(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """List all files currently in the document library."""
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
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
async def docs_library_delete(
    name: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Delete a single file from the library by its basename."""
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
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
    path: str,
    limit: int = DEFAULT_BROWSE_LIMIT,
    recursive: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Browse directories with optional recursion.

    Validates path for traversal attempts and returns entries
    with a safe ``name`` field for front-end consumption.
    """
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
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
    payload: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Create a folder inside the library directory."""
    user_info = auth_middleware(credentials)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authentication required",
            },
        )
    """Create a new folder in the docs directory.
    Expects JSON body with 'path' (parent directory) and 'name' (folder name).
    """
    request_id = str(uuid.uuid4())
    parent_path = payload.get("path")
    folder_name = payload.get("name")

    try:
        # Validate input types
        if not isinstance(parent_path, str) or not isinstance(
            folder_name, str
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
                        "Folder name cannot be empty or whitespace only"
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
                    "message": (
                        f"'{folder_name}' is a reserved Windows name"
                    ),
                    "request_id": request_id,
                },
            )

        # Validate parent path
        parent_path = os.path.normpath(parent_path).lstrip(os.sep)
        if ".." in parent_path.split(os.sep):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid path",
                    "message": "Parent path contains traversal attempt",
                    "request_id": request_id,
                },
            )

        # Resolve paths
        library = _library_dir()
        try:
            target_parent = (library / parent_path).resolve()
            target_parent.relative_to(library.resolve())
        except (OSError, ValueError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid path",
                    "message": "Parent path is outside library",
                    "request_id": request_id,
                },
            )

        # Create folder
        new_folder = target_parent / folder_name
        try:
            new_folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Folder creation failed",
                    "message": str(e),
                    "request_id": request_id,
                },
            )

        return {
            "created": str(new_folder),
            "name": folder_name,
            "path": str(target_parent),
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
    except Exception:
        logger.exception(
            f"[{request_id}] docs_create_folder failed"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Folder creation failed",
                "message": "Internal server error",
                "request_id": request_id,
            },
        )


@app.post("/api/uar/query-code")
async def query_code(
    body: dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Ask a natural-language question about the codebase via Greptile.

    Requires ``GREPTILE_API_KEY`` env var. Falls back to a mock
    response when not configured so the endpoint is always callable.
    """
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
        )
    except Exception as e:
        logger.error(f"Greptile query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "greptile_error",
                "message": str(e),
            },
        )
