"""Shared runtime state for the UAR API.

This module centralises mutable server state, constants, and lazily
resolved services so routers/middleware can import them without
instantiating their own copies.
"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Callable, Dict

from uar.config import _uar_start_time
from uar.container import (
    ServiceContainer,
    WebSocketConnectionCounter,
    get_container,
    reset_container as _reset_service_container,
    set_container as _set_service_container,
)

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
# Service container + lazy proxies
# ------------------------------------------------------------------

_CONTAINER: ServiceContainer | None = None


def _get_container() -> ServiceContainer:
    global _CONTAINER
    if _CONTAINER is None:
        _CONTAINER = get_container()
    return _CONTAINER


def set_service_container(container: ServiceContainer) -> None:
    """Override the global service container (primarily for tests)."""

    global _CONTAINER
    _set_service_container(container)
    _CONTAINER = container


def reset_service_container() -> None:
    """Reset to the default container configuration."""

    global _CONTAINER
    _reset_service_container()
    _CONTAINER = None


def get_service_container() -> ServiceContainer:
    """Return the active service container."""

    return _get_container()


class _LazyProxy:
    """Lazily resolves a service on every attribute access."""

    def __init__(self, getter: Callable[[], Any]) -> None:
        object.__setattr__(self, "_getter", getter)

    def _target(self):
        return object.__getattribute__(self, "_getter")()

    def __getattribute__(self, name: str) -> Any:
        if name in {"_getter", "_target", "__class__"}:
            if name == "__class__":
                return object.__getattribute__(self, "_target")().__class__
            return object.__getattribute__(self, name)
        return getattr(self._target(), name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._target(), name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._target()(*args, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return repr(self._target())

    def __bool__(self) -> bool:  # pragma: no cover - truthiness
        return bool(self._target())


def _store_getter():
    return _get_container().get_store()


def _auth_getter():
    return _get_container().get_auth_service()


def _event_getter():
    return _get_container().get_event_service()


def _exec_getter():
    return _get_container().get_execution_service()


def _ws_counter_getter():
    return _get_container().get_ws_counter()


# Re-export canonical source of truth for backwards compatibility
_uar_start_time = _uar_start_time  # noqa: F811

store = _LazyProxy(_store_getter)
_auth_svc = _LazyProxy(_auth_getter)
_event_svc = _LazyProxy(_event_getter)
_exec_svc = _LazyProxy(_exec_getter)
_ws_conn_counter = _LazyProxy(_ws_counter_getter)

# Backwards-compatible alias for tests importing from uar.api.server
_WebSocketConnectionCounter = WebSocketConnectionCounter
