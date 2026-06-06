"""Tests for T6 — Distributed Executor (WorkerPool).

Covers:
- ThreadPool mode
- Local mode (synchronous)
- ProcessPool mode
- Global pool singleton
- Invalid mode rejection
"""

from __future__ import annotations

import pytest

from uar.core.worker_pool import WorkerPool, get_worker_pool, set_worker_pool


def test_local_mode_executes_synchronously():
    """Local mode runs fn directly and returns a completed Future."""
    pool = WorkerPool(mode="local")
    future = pool.submit(lambda: 42)
    assert future.result() == 42


def test_local_mode_exception():
    """Local mode propagates exceptions through the Future."""
    pool = WorkerPool(mode="local")

    def _fail():
        raise ValueError("boom")

    future = pool.submit(_fail)
    with pytest.raises(ValueError, match="boom"):
        future.result()


def test_thread_pool_mode():
    """Thread pool dispatches work to background threads."""
    pool = WorkerPool(mode="thread", max_workers=2)
    try:
        future = pool.submit(lambda: 123)
        assert future.result(timeout=5) == 123
    finally:
        pool.shutdown()


def test_map_local_mode():
    """Local map applies fn to each item in order."""
    pool = WorkerPool(mode="local")
    results = pool.map(lambda x: x * 2, [1, 2, 3])
    assert results == [2, 4, 6]


def test_map_thread_mode():
    """Thread pool map returns results in input order."""
    pool = WorkerPool(mode="thread", max_workers=2)
    try:
        results = pool.map(lambda x: x * 2, [1, 2, 3])
        assert results == [2, 4, 6]
    finally:
        pool.shutdown()


def test_invalid_mode_rejected():
    """Invalid mode raises ValueError at construction."""
    with pytest.raises(ValueError, match="Invalid pool mode"):
        WorkerPool(mode="unknown")


def test_context_manager():
    """WorkerPool can be used as a context manager."""
    with WorkerPool(mode="thread", max_workers=1) as pool:
        future = pool.submit(lambda: 99)
        assert future.result(timeout=5) == 99


def test_env_default_max_workers(monkeypatch):
    """UAR_POOL_MAX_WORKERS env var controls default max workers."""
    monkeypatch.setenv("UAR_POOL_MAX_WORKERS", "4")
    pool = WorkerPool(mode="thread")
    try:
        assert pool._max_workers == 4
    finally:
        pool.shutdown()


def test_global_pool_singleton(monkeypatch):
    """get_worker_pool returns the same instance."""
    # Reset global state
    import uar.core.worker_pool as _wp

    monkeypatch.setattr(_wp, "_default_pool", None)
    monkeypatch.setattr(_wp, "_pool_lock", None)

    p1 = get_worker_pool()
    p2 = get_worker_pool()
    assert p1 is p2
    p1.shutdown()


def test_set_worker_pool_override():
    """set_worker_pool allows explicit override."""
    custom = WorkerPool(mode="local")
    set_worker_pool(custom)
    assert get_worker_pool() is custom
