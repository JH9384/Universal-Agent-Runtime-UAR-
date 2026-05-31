"""Shared runtime state for the UAR API.

This module centralises mutable server state, constants, and service
instances so that routers and middleware can import them without
relying on :mod:`uar.api.server` directly.
"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict

from uar.memory.json_store import JsonRunStore
from uar.services import AuthService, EventService, GoalExecutionService

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB

CHUNK_SIZE = 1024 * 64  # 64KB
DEFAULT_BROWSE_LIMIT = 200
BACKPRESSURE_DELAY = 0.1  # seconds
SHUTDOWN_SLEEP = max(
    0.0,
    float(
        os.getenv("SHUTDOWN_GRACE_SECONDS", "30").strip() or "30"
    ),
)  # seconds to drain active requests

# SSE connection limit
_MAX_CONCURRENT_SSE_PER_IP = max(
    0, int(os.getenv("UAR_MAX_SSE_PER_IP", "5").strip() or "5")
)
_sse_connections: Dict[str, int] = {}
_sse_connections_lock = asyncio.Lock()

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

# ------------------------------------------------------------------
# Idempotency cache: key -> (timestamp, result)
# Bounded LRU with TTL — eviction runs on every write.
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# WebSocket connection cap
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Run store backend (auto-selected via UAR_STORE_BACKEND)
# ------------------------------------------------------------------
_UAR_STORE_BACKEND = os.getenv("UAR_STORE_BACKEND", "auto").lower()
if _UAR_STORE_BACKEND == "postgres" or (
    _UAR_STORE_BACKEND == "auto" and os.getenv("UAR_DATABASE_URL")
):
    from uar.memory.postgres_store import PostgresRunStore

    store = PostgresRunStore()  # type: ignore[assignment]
elif _UAR_STORE_BACKEND == "sqlite" or (
    _UAR_STORE_BACKEND == "auto"
    and os.getenv("UAR_SQLITE_PATH")
):
    from uar.memory.sqlite_store import SqliteRunStore

    store = SqliteRunStore()  # type: ignore[assignment]
else:
    store = JsonRunStore()  # type: ignore[assignment]

# ------------------------------------------------------------------
# Service instances (stateless, safe to share across requests)
# ------------------------------------------------------------------
_auth_svc = AuthService()
_event_svc = EventService()
_exec_svc = GoalExecutionService(
    event_service=_event_svc,
    store=store,  # type: ignore[arg-type]
    max_stream_events=MAX_STREAM_EVENTS,
    event_buffer_size=EVENT_BUFFER_SIZE,
)
