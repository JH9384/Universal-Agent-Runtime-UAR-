import logging
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version
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
from uar.api.exception_handlers import register_exception_handlers
from uar.api.goal_builder import _build_goal  # noqa: F401
from uar.api.lifespan import create_lifespan
from .middleware import (
    apply_middleware,
    require_auth,
    register_metrics_middleware,
)

# Re-export all shared state for backward compatibility with tests
# that patch names in uar.api.server.
from uar.api.state import (  # noqa: F401
    MAX_UPLOAD_BYTES,
    _MAX_CONCURRENT_SSE_PER_IP,
    _sse_connections,
    _sse_connections_lock,
    _idempotency_cache,
    _IDEMPOTENCY_TTL,
    _IDEMPOTENCY_MAX,
    _idempotency_lock,
    _idempotency_get,
    _idempotency_set,
    _WebSocketConnectionCounter,
    _ws_conn_counter,
    CHUNK_SIZE,
    DEFAULT_BROWSE_LIMIT,
    BACKPRESSURE_DELAY,
    SHUTDOWN_SLEEP,
    WS_HEARTBEAT_INTERVAL,
    WS_HEARTBEAT_TIMEOUT,
    WS_BATCH_SIZE,
    WS_BATCH_TIMEOUT,
    MAX_STREAM_EVENTS,
    EVENT_BUFFER_SIZE,
    store,
    _auth_svc,
    _event_svc,
    _exec_svc,
)

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


import uar.skills  # noqa — registers all standard skills

# Validate canonical recipe skill references now that all skills are
# registered in the global registry.
from uar.core.recipes import validate_recipes  # noqa

validate_recipes()


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
    lifespan=create_lifespan(_ws_conn_counter),
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
register_metrics_middleware(app)


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
# Auth is handled per-endpoint in docs.py to allow anonymous read-only
# access in development mode while keeping write operations protected.
app.include_router(docs_router)

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

register_exception_handlers(app)
