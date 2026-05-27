"""Async utilities shared across the UAR codebase.

Provides :func:`run_sync_safe` — a single, correct entry-point for
running an async coroutine from synchronous code regardless of whether
an event loop is already running (e.g. inside FastAPI/uvicorn).

Usage::

    from uar.core.async_utils import run_sync_safe

    result = run_sync_safe(some_async_fn(arg1, arg2))

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
import concurrent.futures
import logging
from typing import Any, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


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

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_in_new_loop, coro)
        return future.result()


def _run_in_new_loop(coro: Coroutine[Any, Any, T]) -> T:
    """Execute *coro* in a brand-new event loop (called from a thread)."""
    try:
        return asyncio.run(coro)
    except BaseException:
        coro.close()
        raise
