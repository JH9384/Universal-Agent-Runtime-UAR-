"""Worker pool for distributed skill execution.

T6 — Distributed Executor: real worker pool

Provides a configurable pool abstraction over concurrent.futures
(ThreadPoolExecutor / ProcessPoolExecutor) that the Executor can
use to dispatch skill tasks.

Modes:
  thread  — shared thread pool (default; low overhead)
  process — process pool for CPU-bound / isolation tasks
  local   — direct in-process call (no pool; for testing)
"""

from __future__ import annotations

import atexit
import concurrent.futures
import logging
import os
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WorkerPool:
    """Reusable worker pool for dispatching skill executions.

    Args:
        mode: "thread" | "process" | "local"
        max_workers: Max concurrent workers (default from env)
        initializer: Optional callable run in each worker at start
        initargs: Tuple passed to initializer
    """

    def __init__(
        self,
        mode: str = "thread",
        max_workers: Optional[int] = None,
        initializer: Optional[Callable] = None,
        initargs: Tuple[Any, ...] = (),
    ) -> None:
        if mode not in ("thread", "process", "local"):
            raise ValueError(
                f"Invalid pool mode {mode!r}. "
                f"Expected 'thread', 'process', or 'local'."
            )
        self.mode = mode
        self._max_workers = max_workers or self._default_max_workers(mode)
        self._initializer = initializer
        self._initargs = initargs
        self._pool: Optional[
            concurrent.futures.ThreadPoolExecutor
            | concurrent.futures.ProcessPoolExecutor
        ] = None
        self._shutdown = False

        if mode != "local":
            self._start_pool()
            atexit.register(self.shutdown)

    @staticmethod
    def _default_max_workers(mode: str) -> int:
        env_key = (
            "UAR_POOL_MAX_WORKERS"
            if mode == "thread"
            else "UAR_PROCESS_POOL_MAX_WORKERS"
        )
        default = 16 if mode == "thread" else os.cpu_count() or 2
        return max(
            1,
            min(
                128,
                int(os.getenv(env_key, str(default)).strip() or str(default)),
            ),
        )

    def _start_pool(self) -> None:
        if self.mode == "thread":
            self._pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers,
                initializer=self._initializer,
                initargs=self._initargs,
            )
        elif self.mode == "process":
            self._pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=self._max_workers,
                initializer=self._initializer,
                initargs=self._initargs,
            )

    def submit(
        self, fn: Callable, *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future:
        """Submit a task to the pool.

        In "local" mode the callable is invoked synchronously and a
        completed Future is returned.
        """
        if self.mode == "local":
            future: concurrent.futures.Future = concurrent.futures.Future()
            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
            return future

        if self._pool is None or self._shutdown:
            raise RuntimeError("WorkerPool has been shut down")

        return self._pool.submit(fn, *args, **kwargs)

    def map(
        self,
        fn: Callable,
        iterable: List[Any],
        timeout: Optional[float] = None,
    ) -> List[Any]:
        """Map fn over iterable, returning results in order."""
        if self.mode == "local":
            return [fn(item) for item in iterable]

        if self._pool is None or self._shutdown:
            raise RuntimeError("WorkerPool has been shut down")

        return list(self._pool.map(fn, iterable, timeout=timeout))

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying executor."""
        if self._pool is not None and not self._shutdown:
            self._pool.shutdown(wait=wait)
            self._shutdown = True

    def __enter__(self) -> WorkerPool:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.shutdown()


# Global default pool — lazily created on first use so module load
# does not spin up threads/processes.
_default_pool: Optional[WorkerPool] = None
_pool_lock: Any = None


def get_worker_pool(
    mode: Optional[str] = None,
    max_workers: Optional[int] = None,
) -> WorkerPool:
    """Return the shared global WorkerPool.

    The first call creates the pool using the current env settings.
    Subsequent calls return the same instance.
    """
    global _default_pool, _pool_lock
    if _pool_lock is None:
        import threading

        _pool_lock = threading.Lock()
    with _pool_lock:
        if _default_pool is None:
            _default_pool = WorkerPool(
                mode=mode or os.getenv("UAR_POOL_MODE", "thread"),
                max_workers=max_workers,
            )
        return _default_pool


def set_worker_pool(pool: WorkerPool) -> None:
    """Override the global default pool (useful for testing)."""
    global _default_pool
    _default_pool = pool
