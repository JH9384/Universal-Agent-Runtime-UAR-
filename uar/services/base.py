"""Base service class providing dependency injection and lifecycle hooks."""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseService:
    """Base class for all UAR services.

    Provides:
    - Dependency injection via constructor
    - Structured logging with request_id propagation
    - Context manager support for resource lifecycle
    """

    def __init__(self, **deps: Any) -> None:
        """Inject dependencies as keyword args.

        Subclasses should declare explicit parameters and pass
        unknown kwargs to super().__init__().
        """
        self._deps = deps
        self._logger = logging.getLogger(self.__class__.__module__)

    def _log(
        self,
        level: str,
        msg: str,
        request_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Structured log with optional request_id."""
        if request_id:
            msg = f"[{request_id}] {msg}"
        getattr(self._logger, level)(msg, extra=extra)

    async def __aenter__(self) -> "BaseService":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """Async context manager exit."""
        pass

    def __enter__(self) -> "BaseService":
        """Sync context manager entry."""
        return self

    def __exit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """Sync context manager exit."""
        pass
