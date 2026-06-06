"""Dependency injection container for UAR runtime services."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from uar.core.data_source_registry import get_data_source_registry
from uar.core.sync_monitor import get_sync_monitor
from uar.memory.json_store import JsonRunStore
from uar.services import AuthService, EventService, GoalExecutionService

logger = logging.getLogger(__name__)

try:  # Optional imports resolved lazily
    from uar.memory.postgres_store import PostgresRunStore
except Exception:  # pragma: no cover - optional dependency
    PostgresRunStore = None  # type: ignore

try:
    from uar.memory.sqlite_store import SqliteRunStore
except Exception:  # pragma: no cover - optional dependency
    SqliteRunStore = None  # type: ignore


class WebSocketConnectionCounter:
    """Async-safe connection limiter shared across transports."""

    def __init__(self, max_connections: int = 0):
        self.max_connections = max_connections
        self.count = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            if self.max_connections > 0 and self.count >= self.max_connections:
                return False
            self.count += 1
            try:
                from uar.api.metrics import get_metrics_collector

                get_metrics_collector().record_connection(+1)
            except Exception:  # pragma: no cover - metrics optional
                logger.debug(
                    "metrics connection increment failed", exc_info=True
                )
            return True

    async def release(self) -> None:
        async with self._lock:
            if self.count > 0:
                self.count -= 1
                try:
                    from uar.api.metrics import get_metrics_collector

                    get_metrics_collector().record_connection(-1)
                except Exception:  # pragma: no cover - metrics optional
                    logger.debug(
                        "metrics connection decrement failed",
                        exc_info=True,
                    )


class ServiceContainer:
    """Lazily constructs and caches runtime-level services."""

    def __init__(
        self,
        *,
        max_stream_events: int = 5000,
        websocket_max_connections: int = 0,
    ) -> None:
        self.max_stream_events = max_stream_events
        self.websocket_max_connections = websocket_max_connections
        self._store = None
        self._auth_service: Optional[AuthService] = None
        self._event_service: Optional[EventService] = None
        self._execution_service: Optional[GoalExecutionService] = None
        self._ws_counter: Optional[WebSocketConnectionCounter] = None

    # ------------------------------------------------------------------
    # Store handling
    # ------------------------------------------------------------------
    def get_store(self):
        if self._store is None:
            self._store = self._build_store()
        return self._store

    def _build_store(self):
        backend = os.getenv("UAR_STORE_BACKEND", "auto").lower()
        if backend == "postgres" or (
            backend == "auto" and os.getenv("UAR_DATABASE_URL")
        ):
            if PostgresRunStore is None:
                raise RuntimeError(
                    "postgres backend requested but unavailable"
                )
            store = PostgresRunStore()
            store_type = "postgres"
        elif backend == "sqlite" or (
            backend == "auto" and os.getenv("UAR_SQLITE_PATH")
        ):
            if SqliteRunStore is None:
                raise RuntimeError(
                    "sqlite backend requested but unavailable"
                )
            store = SqliteRunStore()
            store_type = "sqlite"
        else:
            store = JsonRunStore()
            store_type = "json"

        get_sync_monitor().register_store("default", store, store_type)
        try:
            get_data_source_registry(store).auto_register_stores()
        except Exception:  # pragma: no cover - optional best effort
            logger.debug("Data source auto-registration failed", exc_info=True)
        return store

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    def get_auth_service(self) -> AuthService:
        if self._auth_service is None:
            self._auth_service = AuthService()
        return self._auth_service

    def get_event_service(self) -> EventService:
        if self._event_service is None:
            self._event_service = EventService()
        return self._event_service

    def get_execution_service(self) -> GoalExecutionService:
        if self._execution_service is None:
            self._execution_service = GoalExecutionService(
                event_service=self.get_event_service(),
                store=self.get_store(),
                max_stream_events=self.max_stream_events,
            )
        return self._execution_service

    def get_ws_counter(self) -> WebSocketConnectionCounter:
        if self._ws_counter is None:
            self._ws_counter = WebSocketConnectionCounter(
                max_connections=self.websocket_max_connections
            )
        return self._ws_counter

    # ------------------------------------------------------------------
    # Testing hooks
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset cached singletons (used by tests)."""

        self._store = None
        self._auth_service = None
        self._event_service = None
        self._execution_service = None
        self._ws_counter = None


_CONTAINER: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    global _CONTAINER
    if _CONTAINER is None:
        max_stream_events = int(
            os.getenv("MAX_STREAM_EVENTS", "5000").strip() or "5000"
        )
        max_ws = int(
            os.getenv("WEBSOCKET_MAX_CONNECTIONS", "0").strip() or "0"
        )
        _CONTAINER = ServiceContainer(
            max_stream_events=max_stream_events,
            websocket_max_connections=max_ws,
        )
    return _CONTAINER


def set_container(container: ServiceContainer) -> None:
    """Override the global container (tests)."""

    global _CONTAINER
    _CONTAINER = container


def reset_container() -> None:
    """Reset container to force lazy re-creation."""

    global _CONTAINER
    _CONTAINER = None
