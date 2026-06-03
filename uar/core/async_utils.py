"""Async utilities shared across the UAR codebase.

Provides :func:`run_sync_safe` — a single, correct entry-point for
running an async coroutine from synchronous code regardless of whether
an event loop is already running (e.g. inside FastAPI/uvicorn).

Also provides :func:`async_lock` — a context manager that acquires a
:cls:`threading.Lock` (or :cls:`threading.RLock`) from async code
without blocking the event loop thread.

Usage::

    from uar.core.async_utils import run_sync_safe, async_lock

    result = run_sync_safe(some_async_fn(arg1, arg2))

    async with async_lock(some_threading_lock):
        do_sync_work()

Why not ``asyncio.run()`` directly?
    ``asyncio.run()`` raises ``RuntimeError: This event loop is already
    running`` when called from within a running loop (e.g. a skill
    invoked by the FastAPI request handler thread-pool). This helper
    detects that case and safely dispatches to a dedicated thread so
    the coroutine always runs to completion — and is **always closed**
    even when an exception occurs.
"""
from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, Coroutine, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")

_LockType = Union[threading.Lock, threading.RLock]

# Shared thread pool for run_sync_safe to avoid creating a new executor
# on every call.  A parallel wave of N async skills would otherwise spin
# up N one-shot ThreadPoolExecutors, wasting memory and startup time.
_RUN_SYNC_MAX = max(
    1,
    min(
        32,
        int(os.getenv("UAR_RUN_SYNC_MAX", "4").strip() or "4"),
    ),
)
_RUN_SYNC_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=_RUN_SYNC_MAX,
    thread_name_prefix="uar_run_sync",
)
atexit.register(_RUN_SYNC_POOL.shutdown, wait=False)


@asynccontextmanager
async def async_lock(lock: _LockType):
    """Acquire a :cls:`threading.Lock` / :cls:`threading.RLock` from async
    code without blocking the event-loop thread.

    The lock is acquired in the default :cls:`ThreadPoolExecutor` so the
    event loop can continue processing other tasks while waiting.  Hold
    times should remain short (microseconds) — long-running critical
    sections still hurt throughput even when off-loaded to a worker.

    Usage::

        async def my_async_fn():
            async with async_lock(my_thread_lock):
                # runs in thread-pool while event loop stays free
                mutate_shared_state()
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lock.acquire)
    try:
        yield
    finally:
        lock.release()


def run_sync_safe(coro: Coroutine[Any, Any, T]) -> T:
    """Run *coro* to completion from synchronous code.

    * If no event loop is running, delegates to ``asyncio.run()``.
    * If a loop is already running (FastAPI / uvicorn worker), submits
      the coroutine to a one-shot ``ThreadPoolExecutor`` thread so it
      gets its own fresh loop — avoiding the ``RuntimeError``.

    The coroutine is **always closed** on exception so async context
    managers and generators inside it are properly torn down.

    Args:
        coro: An unawaited coroutine object.

    Returns:
        Whatever the coroutine returns.

    Raises:
        Any exception raised by the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _RUN_SYNC_POOL.submit(_run_in_new_loop, coro)
    return future.result()


def _run_in_new_loop(coro: Coroutine[Any, Any, T]) -> T:
    """Execute *coro* in a brand-new event loop (called from a thread)."""
    try:
        return asyncio.run(coro)
    except BaseException:
        coro.close()
        raise
