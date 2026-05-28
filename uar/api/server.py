import json
import logging
import os
import threading
import time
import uuid
import asyncio
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.websockets import WebSocketState
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import ValidationError as PydanticValidationError

from uar.api.models import RunRequest, ErrorResponse
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
from uar.api.advanced_endpoints import router as advanced_router
# Re-exported for backward compatibility with tests that patch them
from uar.api.responses import error_response  # noqa: F401
from uar.api.routers.health import router as health_router
from uar.api.routers.recipes import router as recipes_router
from uar.api.routers.recipes import (  # noqa: F401
    _recipe_svc,
    _recipe_http_error,
)
from uar.api.routers.cache_sandbox import router as cache_sandbox_router
from uar.api.routers.metrics import router as metrics_router
from uar.api.routers.metrics import _check_metrics_auth  # noqa: F401
from uar.api.routers.docs import router as docs_router
from uar.api.routers.docs import (  # noqa: F401
    _resolve_docs_path,
    _library_dir,
    _cleanup_orphaned_temp_files,
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
_MAX_CONCURRENT_SSE_PER_IP = max(
    0, int(os.getenv("UAR_MAX_SSE_PER_IP", "5").strip() or "5")
)
_sse_connections: Dict[str, int] = {}
_sse_connections_lock = asyncio.Lock()

# Idempotency cache: key -> (timestamp, result)
# Bounded LRU with TTL — eviction runs on every write.
_idempotency_cache: Dict[str, Any] = {}
_IDEMPOTENCY_TTL = max(
    0,
    int(os.getenv("UAR_IDEMPOTENCY_TTL", "86400").strip() or "86400"),
)  # 24h
_IDEMPOTENCY_MAX = max(
    1, int(os.getenv("UAR_IDEMPOTENCY_MAX", "1000").strip() or "1000")
)
_idempotency_lock = threading.Lock()


def _idempotency_get(key: str) -> Any:
    """Return cached result if key exists and has not expired, else None."""
    with _idempotency_lock:
        entry = _idempotency_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > _IDEMPOTENCY_TTL:
        with _idempotency_lock:
            _idempotency_cache.pop(key, None)
        return None
    return result


def _idempotency_set(key: str, result: Any) -> None:
    """Store result under key, evicting expired and excess entries."""
    now = time.time()
    with _idempotency_lock:
        _idempotency_cache[key] = (now, result)
        # Evict expired entries first
        expired = [
            k for k, (ts, _) in _idempotency_cache.items()
            if now - ts > _IDEMPOTENCY_TTL
        ]
        for k in expired:
            _idempotency_cache.pop(k, None)
        # If still over cap, drop oldest by insertion order (FIFO)
        while len(_idempotency_cache) > _IDEMPOTENCY_MAX:
            oldest = next(iter(_idempotency_cache))
            _idempotency_cache.pop(oldest, None)


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
        async with self.lock:
            if (
                self.max_connections > 0
                and self.count >= self.max_connections
            ):
                return False
            self.count += 1
            from uar.api.metrics import get_metrics_collector
            get_metrics_collector().record_connection(+1)
            return True

    async def release(self) -> None:
        async with self.lock:
            if self.count > 0:
                self.count = max(0, self.count - 1)
                from uar.api.metrics import get_metrics_collector

                get_metrics_collector().record_connection(-1)


_ws_conn_counter = _WebSocketConnectionCounter(
    max(0, int(os.getenv("WEBSOCKET_MAX_CONNECTIONS", "0").strip() or "0"))
)
CHUNK_SIZE = 1024 * 64  # 64KB
DEFAULT_BROWSE_LIMIT = 200
BACKPRESSURE_DELAY = 0.1  # seconds
SHUTDOWN_SLEEP = max(
    0.0,
    float(
        os.getenv("SHUTDOWN_GRACE_SECONDS", "30").strip() or "30"
    ),
)  # seconds to drain active requests


# WebSocket robustness constants (used by the batch+heartbeat WS handler)
WS_HEARTBEAT_INTERVAL = max(
    1.0,
    float(
        os.getenv("UAR_WS_HEARTBEAT_INTERVAL", "20").strip() or "20"
    ),
)
WS_HEARTBEAT_TIMEOUT = 60.0  # seconds without pong before disconnect
WS_BATCH_SIZE = max(
    1, int(os.getenv("UAR_WS_BATCH_SIZE", "10").strip() or "10")
)
WS_BATCH_TIMEOUT = max(
    0.001,
    float(
        os.getenv("UAR_WS_BATCH_TIMEOUT", "0.05").strip() or "0.05"
    ),
)

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
    from uar.memory.base_store import get_store
    from uar.config import config

    if config.run_retention_days <= 0:
        return

    import asyncio

    store = get_store()
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

    # Production security checks
    if _is_production:
        if not CORS_ORIGINS or CORS_ORIGINS == [""]:
            logger.warning(
                "CORS_ORIGINS is not configured in production. "
                "All cross-origin requests will be blocked."
            )
        sec_headers = os.getenv("SECURITY_HEADERS", "").lower()
        if sec_headers != "enabled":
            logger.warning(
                "SECURITY_HEADERS not enabled in production. "
                "Consider setting SECURITY_HEADERS=enabled."
            )

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
    # Shutdown metrics collector flush thread
    try:
        get_metrics_collector().shutdown()
    except Exception:
        logger.exception("Metrics collector shutdown failed")
    # Shutdown Postgres connection pool if active
    try:
        from uar.memory.postgres_store import _shutdown_postgres_pool

        _shutdown_postgres_pool()
    except Exception:
        logger.exception("Postgres pool shutdown failed")
    # Close per-domain aiohttp sessions
    try:
        from uar.core.http_client import close_all_sessions

        close_all_sessions()
    except Exception:
        logger.exception("HTTP sessions close failed")
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
    version=get_uar_version(),
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
    minimum_size=max(
        0, int(os.getenv("UAR_GZIP_MIN_SIZE", "1024").strip() or "1024")
    ),
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

# Include health / metrics / status router
app.include_router(health_router)

# Include recipe CRUD router (endpoints handle auth individually)
app.include_router(recipes_router)

# Include cache and sandbox router
app.include_router(cache_sandbox_router, dependencies=[Depends(require_auth)])

# Include metrics router (public /metrics, auth-protected /api/metrics)
app.include_router(metrics_router)

# Include document library router
app.include_router(docs_router, dependencies=[Depends(require_auth)])

# Include run execution and query router
from uar.api.routers.runs import router as runs_router  # noqa: E402

app.include_router(runs_router)

# Include consolidated UOR object/runtime/agent router (formerly
# apps/api-python/main.py).
from uar.api.routers import uor_router  # noqa: E402

app.include_router(uor_router, dependencies=[Depends(require_auth)])

# Auto-select run store backend
if os.getenv("UAR_DATABASE_URL"):
    from uar.memory.postgres_store import PostgresRunStore
    store = PostgresRunStore()  # type: ignore[assignment]
else:
    store = JsonRunStore()  # type: ignore[assignment]


# Custom exception handlers for UAR exceptions

@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    field = getattr(exc, "field", None)
    if field == "input_path":
        message = "Invalid path provided"
    elif field == "goal":
        message = "Invalid goal provided"
    elif field == "skills":
        message = "Invalid skills provided"
    elif field == "timeout_seconds":
        message = "Invalid timeout provided"
    elif field == "execution_order":
        message = "Invalid execution order provided"
    else:
        message = "Invalid input provided"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "Validation error",
                "code": exc.code.value,
                "message": message,
                "field": field,
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
                "message": "Invalid path provided",
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
                "message": "An internal error occurred",
            }
        },
    )


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

    serializer = serializers.get(skill or "")
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
    _ws_pre_allowed, _ws_pre_remaining = rate_limiter.is_allowed(
        rate_limit_key, limit, window
    )
    if not _ws_pre_allowed:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return

    # Enforce global WebSocket connection cap
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return

    try:
        await websocket.accept()
    except Exception:
        await _ws_conn_counter.release()
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
        websocket_timeout = max(
            1,
            int(
                os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30").strip()
                or "30"
            ),
        )
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(), timeout=websocket_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] WebSocket receive timeout after %ss",
                request_id,
                websocket_timeout,
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": "No data received within timeout",
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
            logger.warning(
                "[%s] WebSocket validation error: %s", request_id, str(e)
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return
        except PydanticValidationError as e:
            logger.warning(
                "[%s] WebSocket pydantic validation error: %s",
                request_id,
                str(e),
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return

        # Skill-specific rate limiting (post-parse, reuses pre-connect
        # token — connection-level check already consumed one token above).
        from uar.api.middleware import check_rate_limit

        skill_name = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )

        limit, window, rate_limit_type = check_rate_limit(
            rate_limit_key, tier, skill_name
        )

        # Only re-check when the skill has a tighter limit than the tier.
        # Avoids double-consuming tokens on the default tier limit.
        allowed = _ws_pre_allowed
        if rate_limit_type == "skill":
            try:
                _rl_result = rate_limiter.is_allowed(
                    rate_limit_key, limit, window
                )
                allowed = bool(_rl_result[0])  # type: ignore[index,assignment]
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
                    await websocket.close(
                        code=1008, reason="Rate limit error"
                    )
                except Exception:
                    logger.warning("WebSocket close failed", exc_info=True)
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
        logger.info(
            "[%s] WebSocket request from %s", request_id, user_str
        )

        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)
            _goal_id = strategy.goal_id

            # WebSocket heartbeat with coalescing
            last_hb = time.time()
            hb_interval = WS_HEARTBEAT_INTERVAL
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
                    except Exception as exc:
                        logger.warning(
                            "[%s] Binary visualization stream failed: %s",
                            request_id, exc,
                        )

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

        except ValidationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Invalid input",
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
                    "error": "Internal server error",
                    "error_type": "InternalError",
                    "request_id": request_id,
                }
            )

    except WebSocketDisconnect:
        logger.info("[%s] WebSocket disconnected", request_id)
    except Exception:
        logger.exception(
            "[%s] WebSocket connection error", request_id,
            extra={
                "request_id": request_id,
                "client_host": (
                    websocket.client.host if websocket.client else "unknown"
                ),
                "authenticated": credentials is not None,
            },
        )
    finally:
        await _ws_conn_counter.release()
        try:
            await websocket.close()
        except Exception:
            logger.warning("WebSocket close failed", exc_info=True)


# Service instances (stateless, safe to share across requests)
_auth_svc = AuthService()
_event_svc = EventService()
_exec_svc = GoalExecutionService(
    event_service=_event_svc,
    store=store,  # type: ignore[arg-type]
    max_stream_events=MAX_STREAM_EVENTS,
    event_buffer_size=EVENT_BUFFER_SIZE,
)


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
                logger.warning(
                    "SSE rate limit exceeded for IP %s "
                    "(limit: %s)",
                    client_ip,
                    _MAX_CONCURRENT_SSE_PER_IP,
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": (
                            "Too many concurrent streaming connections. "
                            "Please try again later."
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
            cid = getattr(request.state, "correlation_id", "")

            _sse_emit = _event_svc.emit_sse

            async def _generate():
                try:
                    goal = _build_goal(req)
                    last_hb = time.time()
                    hb_interval = WS_HEARTBEAT_INTERVAL
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
                            error_msg="Stream error",
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
            logger.warning("[%s] Stream validation error: %s", request_id, e)
            # Provide user-friendly error messages based on field
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
            )
        except UARError as e:
            logger.error("[%s] Stream UAR error: %s", request_id, e)
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
                    "message": "Request failed",
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
        await _ws_conn_counter.release()
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

        websocket_timeout = max(
            1,
            int(
                os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30").strip()
                or "30"
            ),
        )
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=websocket_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] WebSocket receive timeout after %ss",
                request_id,
                websocket_timeout,
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": "No data received within timeout",
                        "request_id": request_id,
                    },
                )
            )
            await websocket.close()
            return
        try:
            req = RunRequest(**data)
        except PydanticValidationError as e:
            logger.warning(
                "[%s] WebSocket pydantic validation error: %s",
                request_id,
                str(e),
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
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
                    except Exception as exc:
                        logger.warning(
                            "[%s] WebSocket send_json dropped event: %s",
                            request_id, exc,
                        )
                    # Stream binary visualization data for 3D skills
                    if ev.get("type") == "skill_complete":
                        try:
                            await _stream_binary_visualization(
                                websocket, ev
                            )
                        except Exception as exc:
                            logger.warning(
                                "[%s] Batch binary visualization failed: %s",
                                request_id, exc,
                            )
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
    except Exception:
        logger.exception("WebSocket error")
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                safe_error = "Internal server error"
                await websocket.send_json(
                    {"type": "error", "error": safe_error}
                )
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to send error frame to client: %s",
                    request_id, exc,
                )
    finally:
        await _ws_conn_counter.release()
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
            logger.warning("WebSocket close failed", exc_info=True)


