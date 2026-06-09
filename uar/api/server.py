import logging
import os
from typing import Any, Dict, List, Optional

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


def _manage_openapi_schema_routes() -> None:
    """Keep OpenAPI generation stable without removing runtime routes.

    Enterprise contract posture:
    - runtime routes remain mounted and executable
    - schema-broken legacy routes are hidden from OpenAPI only
    - hidden route paths are retained in app.state.openapi_excluded_routes
      for audit and follow-up normalization
    """
    try:
        from fastapi.routing import APIRoute
    except Exception:
        return

    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "dict": dict,
        "list": list,
    }
    excluded: list[str] = []

    def field_is_schema_safe(field: Any) -> bool:
        if field is None:
            return True
        adapter = getattr(field, "_type_adapter", None)
        rebuild = getattr(adapter, "rebuild", None)
        if not callable(rebuild):
            return True
        try:
            rebuild(_types_namespace=namespace, force=True)
            return True
        except TypeError:
            try:
                rebuild(_types_namespace=namespace)
                return True
            except TypeError:
                try:
                    rebuild()
                    return True
                except Exception:
                    return False
            except Exception:
                return False
        except Exception:
            return False

    def route_schema_fields(route: Any) -> list[Any]:
        fields: list[Any] = [
            getattr(route, "body_field", None),
            getattr(route, "response_field", None),
            getattr(route, "secure_cloned_response_field", None),
        ]
        fields.extend((getattr(route, "response_fields", None) or {}).values())
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            for attr in (
                "path_params",
                "query_params",
                "header_params",
                "cookie_params",
                "body_params",
            ):
                fields.extend(getattr(dependant, attr, []) or [])
        return fields

    for route in getattr(app, "routes", []):
        if not isinstance(route, APIRoute):
            continue
        if all(field_is_schema_safe(field) for field in route_schema_fields(route)):
            continue
        route.include_in_schema = False
        excluded.append(getattr(route, "path", "<unknown>"))

    app.state.openapi_excluded_routes = excluded
    if excluded:
        logger.warning(
            "Excluded %s schema-broken route(s) from OpenAPI: %s",
            len(excluded),
            ", ".join(excluded),
        )


_manage_openapi_schema_routes()
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
