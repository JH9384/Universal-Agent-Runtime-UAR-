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
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from uar.api.models import RunRequest
from uar.core.contracts import GoalSpec
from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version
from uar.core.exceptions import UARError, ValidationError, PathSecurityError
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
from .middleware import auth_middleware, apply_middleware
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

# Include streaming router (WebSocket + SSE)
from uar.api.routers.streaming import router as streaming_router  # noqa: E402

app.include_router(streaming_router)

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


# Service instances (stateless, safe to share across requests)
_auth_svc = AuthService()
_event_svc = EventService()
_exec_svc = GoalExecutionService(
    event_service=_event_svc,
    store=store,  # type: ignore[arg-type]
    max_stream_events=MAX_STREAM_EVENTS,
    event_buffer_size=EVENT_BUFFER_SIZE,
)
