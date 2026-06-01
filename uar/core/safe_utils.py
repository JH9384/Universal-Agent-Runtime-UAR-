"""Safe utility patterns that prevent recurring bug categories.

This module codifies guardrails for the most frequent bug patterns
found across bug-bounty sessions:

1. Silent exception swallowing  →  ``swallow`` context manager
2. wall-clock timeout drift   →  ``monotonic_timeout``
3. f-string logging            →  ``SafeLogger`` wrapper
4. getattr silent fallback     →  ``safe_getattr`` with audit
5. lru_cache on methods        →  ``class_lru_cache`` descriptor
"""

from __future__ import annotations

import functools
import logging
import threading
import time
import collections
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1.  Silent-exception guard
# ---------------------------------------------------------------------------

@contextmanager
def swallow(
    log: Optional[logging.Logger] = None,
    msg: str = "Swallowed exception",
    level: str = "warning",
    return_value: Any = None,
):
    """Context manager that catches *all* exceptions, logs them, and
    optionally returns a default value.

    Usage (replaces bare ``except Exception: return None``)::

        with swallow(return_value=None):
            risky_operation()

    Or with custom logging::

        with swallow(log, "Cache get failed", return_value=0):
            return cache.get(key)
    """
    _log = log or logger
    try:
        yield return_value
    except Exception as exc:
        try:
            log_method = getattr(_log, level)
        except AttributeError:
            _log.warning(
                "swallow: invalid log level %r, falling back to warning",
                level,
            )
            log_method = _log.warning
        log_method("%s: %s", msg, exc, exc_info=True)


# ---------------------------------------------------------------------------
# 2.  Monotonic-timeout guard
# ---------------------------------------------------------------------------

class MonotonicDeadline:
    """Deadline helper using ``time.monotonic()`` to avoid NTP drift.

    Replaces the common anti-pattern (wall-clock time used for timeout) ::

    With::

        d = MonotonicDeadline(timeout)
        while not d.expired: ...
    """

    def __init__(self, timeout: float) -> None:
        self._deadline = time.monotonic() + timeout
        self._timeout = timeout

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self._deadline

    @property
    def remaining(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def __float__(self) -> float:
        return self.remaining


@contextmanager
def monotonic_timeout(timeout: float, *, label: str = "operation"):
    """Yield a ``MonotonicDeadline`` and enforce that the block completes
    within *timeout* seconds.

    If the block exceeds the deadline a ``TimeoutError`` is raised.
    """
    deadline = MonotonicDeadline(timeout)
    try:
        yield deadline
    except Exception:
        if deadline.expired:
            # The caught exception is the interrupted work, not the
            # cause of the timeout.  Log it so the root cause is not
            # completely lost, then suppress chaining so the
            # TimeoutError stands on its own.
            logger.warning(
                "monotonic_timeout: operation '%s' exceeded %ss; "
                "converting to TimeoutError (original exception suppressed)",
                label,
                timeout,
                exc_info=True,
            )
            raise TimeoutError(
                f"{label} exceeded {timeout}s (monotonic)"
            ) from None
        raise
    if deadline.expired:
        raise TimeoutError(
            f"{label} exceeded {timeout}s (monotonic)"
        )


# ---------------------------------------------------------------------------
# 3.  Safe getattr (audit fallback usage)
# ---------------------------------------------------------------------------

_SENTINEL = object()


def safe_getattr(
    obj: Any,
    name: str,
    *fallbacks: str,
    default: Any = _SENTINEL,
    log: Optional[logging.Logger] = None,
) -> Any:
    """Like ``getattr`` but accepts a *chain* of candidate names and
    warns when a fallback is used.

    This prevents the silent-data-corruption bug where::

        getattr(record, "id", "")          # always ""

    is used on an object whose field is actually ``run_id``.  With
    ``safe_getattr``::

        safe_getattr(record, "run_id", "id", default="")

    logs a warning if ``"id"`` is hit, alerting maintainers that the
    object schema may be drifting.
    """
    names = (name,) + fallbacks
    for cand in names:
        try:
            val = getattr(obj, cand, _SENTINEL)
        except Exception:
            val = _SENTINEL
        if val is not _SENTINEL:
            if cand != name and log is not False:
                (log or logger).warning(
                    "safe_getattr fallback used: %s.%s (wanted %s)",
                    type(obj).__name__,
                    cand,
                    name,
                )
            return val
    if default is _SENTINEL:
        raise AttributeError(
            f"{type(obj).__name__!r} object has no attribute in {names!r}"
        )
    return default


# ---------------------------------------------------------------------------
# 4.  SafeLogger — reject f-string logging at runtime in debug builds
# ---------------------------------------------------------------------------

class _SafeLogger:
    """Proxy that wraps a stdlib ``Logger`` and validates that
    ``msg`` is not an f-string in DEBUG builds.

    Because f-string detection is expensive, it is only enabled when
    the env var ``UAR_STRICT_LOGGING=1`` is set (CI, pre-commit).
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _check(self, msg: str) -> None:
        import os
        import re

        if os.getenv("UAR_STRICT_LOGGING") != "1":
            return
        # Heuristic: flag only brace pairs that contain what looks like
        # a Python identifier or expression, e.g. {var} or {obj.attr}.
        # This avoids false positives on JSON, empty {}, or numeric
        # format specs like {0}.
        if "%" in msg:
            return
        if re.search(r"\{[A-Za-z_]", msg):
            raise RuntimeError(
                f"f-string detected in logger call: {msg[:80]!r}"
            )

    def debug(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.debug(msg, *args, **kw)

    def info(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.info(msg, *args, **kw)

    def warning(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.warning(msg, *args, **kw)

    def error(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.error(msg, *args, **kw)

    def critical(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.critical(msg, *args, **kw)

    def exception(self, msg: str, *args: Any, **kw: Any) -> None:
        self._check(msg)
        self._logger.exception(msg, *args, **kw)

    @property
    def underlying(self) -> logging.Logger:
        return self._logger


def get_safe_logger(name: str) -> _SafeLogger:
    """Return a ``_SafeLogger`` wrapping ``logging.getLogger(name)``."""
    return _SafeLogger(logging.getLogger(name))


# ---------------------------------------------------------------------------
# 5.  Re-entrant lock with automatic release tracking
# ---------------------------------------------------------------------------

class TrackedLock:
    """Thin wrapper around ``threading.Lock`` / ``threading.RLock`` that
    remembers whether *this* thread currently holds the lock.

    Helps prevent the leak pattern where ``acquire()`` is called inside
    ``try`` but ``release()`` is forgotten in ``finally``::

        lock = TrackedLock()
        with lock:
            ...

    The context-manager form is always preferred.
    """

    def __init__(self, rlock: bool = False) -> None:
        _cls = threading.RLock if rlock else threading.Lock
        self._lock: threading.Lock = _cls()  # type: ignore[assignment]
        self._depth = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        ok = self._lock.acquire(blocking, timeout)
        if ok:
            self._depth += 1
        return ok

    def release(self) -> None:
        self._lock.release()
        self._depth -= 1

    @property
    def held(self) -> bool:
        return self._depth > 0

    def __enter__(self) -> TrackedLock:
        self.acquire()
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()


# ---------------------------------------------------------------------------
# 6.  lru_cache on bound methods — safe descriptor
# ---------------------------------------------------------------------------

class class_lru_cache(Generic[T]):
    """Descriptor that attaches an ``lru_cache`` to a *class*, not to
    individual instances, preventing the memory-leak pattern where each
    ``MyClass()`` creates a new cache that holds a reference to ``self``.

    **Only safe for pure methods** that do not depend on mutable instance
    state.  The cache is shared across all instances of the same class.

    Usage::

        class SimplePlanner:
            @class_lru_cache(maxsize=1024)
            def plan(
                self, goal_id: str, required_skills: tuple
            ) -> StrategySpec:
                ...
    """

    def __init__(self, maxsize: int = 128) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be a positive integer")
        self._maxsize = maxsize
        self._cache: Dict[type, Dict[Any, Any]] = {}
        self._order: Dict[type, Any] = {}
        self._lock = threading.Lock()
        self._fn: Optional[Callable[..., T]] = None

    def __call__(self, fn: Callable[..., T]) -> class_lru_cache[T]:
        self._fn = fn
        return self

    def __get__(
        self, instance: Any, owner: type[Any]
    ) -> Callable[..., T]:
        if instance is None:
            return self._fn  # type: ignore[return-value]

        with self._lock:
            if owner not in self._cache:
                self._cache[owner] = {}
                self._order[owner] = collections.OrderedDict()

        cache = self._cache[owner]
        order = self._order[owner]
        maxsize = self._maxsize
        _fn = self._fn
        assert _fn is not None

        @functools.wraps(_fn)
        def _cached(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            with self._lock:
                if key in cache:
                    order.move_to_end(key)
                    return cache[key]
            result = _fn(instance, *args, **kwargs)
            with self._lock:
                if key in cache:
                    return cache[key]
                cache[key] = result
                order[key] = None
                if len(order) > maxsize:
                    oldest, _ = order.popitem(last=False)
                    del cache[oldest]
                return result

        return _cached
