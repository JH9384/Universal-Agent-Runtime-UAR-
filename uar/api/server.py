import logging
import os
from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version

# Re-exported for backward compatibility with tests that patch them
from uar.api.responses import error_response  # noqa: F401
from uar.api.routers.recipes import (  # noqa: F401
    _recipe_svc,
    _recipe_http_error,
)
from uar.api.routers.metrics import _check_metrics_auth  # noqa: F401
from uar.api.routers.docs import (  # noqa: F401
    _resolve_docs_path,
    _library_dir,
    _cleanup_orphaned_temp_files,
)
from uar.api.goal_builder import _build_goal  # noqa: F401
from .middleware import require_auth  # noqa: F401

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

# Delegate app creation to the unified boot module.
from uar.boot import create_app  # noqa: E402

app = create_app()
logger.info(
    "UAR API server module ready (%s, UOR %s)",
    get_uar_version(),
    get_uor_version(),
)

# Backward-compatible module-level CORS values (tests patch these)
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
