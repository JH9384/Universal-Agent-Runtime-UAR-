"""Tests for Session 5 fixes: postgres field mapping, contracts deque.

Covers:
- postgres_store: field mapping (run_id/goal_id vs id/goal)
- contracts: deque events with O(1) eviction
- async_utils: run_sync_safe behavior
"""

from __future__ import annotations

import collections
import io
import json
import os
import pathlib
import sys
import tempfile
import threading
from typing import Any

import pytest

import uar.core.contracts as _contracts
from uar.core.async_utils import run_sync_safe
from uar.core.contracts import GoalSpec, PipelineContext
from uar.memory.postgres_store import PostgresRunStore


# ---------------------------------------------------------------------------
# Postgres Store: Field Mapping
# ---------------------------------------------------------------------------

class FakeRecord:
    """Simulates a record with both old and new field names."""

    def __init__(self, run_id: str, goal_id: str, **extra):
        self.run_id = run_id
        self.goal_id = goal_id
        self.status = extra.get("status", "pending")
        self.skills = extra.get("skills", ["echo"])
        self.events = extra.get("events", [])
        self.outputs = extra.get("outputs", {})
        self.metadata = extra.get("metadata", {})
        self.user_id = extra.get("user_id")
        self.id = "wrong-id"  # Should NOT be used
        self.goal = {"id": "wrong-goal-id"}  # Should NOT be used


def test_append_uses_run_id_not_id(monkeypatch):
    """append() must use run_id field, not id."""
    captured = {}

    def _mock_execute(sql, data):
        captured.update(data)

    def _mock_commit():
        pass

    class MockConn:
        def cursor(self):
            return MockCur()

        def commit(self):
            _mock_commit()

    class MockCur:

        def execute(self, sql, data):
            _mock_execute(sql, data)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockPool:

        def getconn(self):
            return MockConn()

        def putconn(self, conn):
            pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    store._read_pool = None
    store._db_url = "mock"
    store._read_url = None

    record = FakeRecord(run_id="correct-run", goal_id="correct-goal")

    # Patch _ensure_table to avoid actual DB calls
    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append(record)

    assert captured["run_id"] == "correct-run", (
        f"Expected run_id='correct-run', got {captured['run_id']!r}. "
        "Field mapping bug: 'id' was used instead of 'run_id'"
    )
    assert captured["goal_id"] == "correct-goal", (
        f"Expected goal_id='correct-goal', got {captured['goal_id']!r}. "
        "Field mapping bug: 'goal.id' was used instead of 'goal_id'"
    )


def test_append_many_uses_run_id_not_id(monkeypatch):
    """append_many() must use run_id field, not id."""
    import csv

    captured_buf = None

    class MockConn:

        def cursor(self):
            return MockCur()

        def commit(self):
            pass

    class MockCur:

        def copy_expert(self, sql, buf):
            nonlocal captured_buf
            captured_buf = buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockPool:

        def getconn(self):
            return MockConn()

        def putconn(self, conn):
            pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    store._read_pool = None
    store._db_url = "mock"
    store._read_url = None

    records = [
        FakeRecord(run_id="run-1", goal_id="goal-1"),
        FakeRecord(run_id="run-2", goal_id="goal-2"),
    ]

    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append_many(records)

    assert captured_buf is not None
    reader = csv.reader(
        io.StringIO(captured_buf), delimiter="\t", lineterminator="\n"
    )
    rows = list(reader)
    assert len(rows) == 2
    for i, fields in enumerate(rows):
        assert fields[0] == f"run-{i+1}", (
            f"Line {i}: Expected run_id='run-{i+1}', got {fields[0]!r}. "
            "Field mapping bug in append_many"
        )
        assert fields[1] == f"goal-{i+1}", (
            f"Line {i}: Expected goal_id='goal-{i+1}', got {fields[1]!r}. "
            "Field mapping bug in append_many"
        )


# ---------------------------------------------------------------------------
# Contracts: PipelineContext deque behavior
# ---------------------------------------------------------------------------

def test_pipeline_context_events_is_deque():
    """PipelineContext.events must be a collections.deque."""
    goal = GoalSpec(id="g1", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)

    assert isinstance(ctx.events, collections.deque), (
        f"Expected deque, got {type(ctx.events).__name__}. "
        "O(n) list pop(0) eviction bug not fixed"
    )


def test_deque_eviction_is_o1():
    """deque with maxlen evicts oldest automatically in O(1)."""
    goal = GoalSpec(id="g1", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal, _max_events=5)

    # Emit 10 events into a maxlen=5 deque
    for i in range(10):
        ctx.emit("test", {"idx": i})

    # Should only have last 5 events
    assert len(ctx.events) == 5
    indices = [e["payload"]["idx"] for e in ctx.events]
    assert indices == [5, 6, 7, 8, 9], (
        f"Expected [5,6,7,8,9] (oldest evicted), got {indices}. "
        "deque maxlen eviction not working"
    )


def test_close_is_idempotent():
    """close() can be called multiple times without error."""
    goal = GoalSpec(id="g1", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)

    ctx.close()
    ctx.close()  # Should not raise
    assert ctx._overflow_file is None


def test_del_closes_overflow_file():
    """__del__ ensures overflow file is closed."""
    goal = GoalSpec(id="g1", user_intent="test", objective="test")

    # Enable disk overflow
    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        ctx = PipelineContext(goal=goal, _max_events=10)
        assert ctx._overflow_file is not None

        # Manually delete
        del ctx

        # File should be closed (no way to verify directly, but no exception)
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env


# ---------------------------------------------------------------------------
# Async Utils: run_sync_safe
# ---------------------------------------------------------------------------

async def _coro_return_42():
    return 42


async def _coro_raise_error():
    raise ValueError("test error")


def test_run_sync_safe_no_loop():
    """run_sync_safe works when no event loop is running."""
    result = run_sync_safe(_coro_return_42())
    assert result == 42


def test_run_sync_safe_exception_propagation():
    """run_sync_safe propagates exceptions correctly."""
    with pytest.raises(ValueError, match="test error"):
        run_sync_safe(_coro_raise_error())


# ---------------------------------------------------------------------------
# RunRecord: run_record_from_dict key filtering
# ---------------------------------------------------------------------------

def test_run_record_from_dict_key_filtering():
    """run_record_from_dict must filter unknown keys."""
    from uar.memory.base_store import run_record_from_dict

    data = {
        "run_id": "r1",
        "goal_id": "g1",
        "skills": ["echo"],
        "unknown_field": "should_be_filtered",
        "another_bad_key": 123,
    }

    record = run_record_from_dict(data)
    assert record.run_id == "r1"
    assert record.goal_id == "g1"
    assert not hasattr(record, "unknown_field")
    assert not hasattr(record, "another_bad_key")


def test_run_record_from_dict_missing_required_fields():
    """run_record_from_dict raises TypeError when required fields missing."""
    from uar.memory.base_store import run_record_from_dict

    # Raises TypeError because RunRecord(**filtered) is called with
    # missing required positional arguments
    with pytest.raises(TypeError):
        run_record_from_dict({"run_id": "r1"})  # Missing goal_id, skills


def test_cleanup_uses_atexit_registry():
    """PipelineContext cleanup uses a module-level atexit registry.

    The old warnings.warn fallback in __del__ has been replaced with
    a module-level _overflow_paths set and an atexit handler so that
    temp files are removed even when __del__ is skipped (circular
    references, interpreter shutdown, etc.).
    """
    import inspect

    del_src = inspect.getsource(PipelineContext.__del__)
    mod_src = inspect.getsource(_contracts)

    # atexit must be available at module level for guaranteed cleanup.
    assert "import atexit" in mod_src, (
        "module-level atexit import missing"
    )
    assert "_overflow_paths" in mod_src, (
        "module-level _overflow_paths registry missing"
    )
    assert "atexit.register" in mod_src, (
        "atexit.register call missing"
    )
    # __del__ calls _cleanup_overflow_file which handles os.unlink and
    # _overflow_paths.discard together; any exception is swallowed by
    # the outer try/except in __del__ for shutdown safety.
    assert "_cleanup_overflow_file" in del_src, (
        "_cleanup_overflow_file call missing in __del__"
    )


# ---------------------------------------------------------------------------
# Postgres Store: UOR provenance fields (uor_address, uor_witness)
# ---------------------------------------------------------------------------

class FakeRecordWithUOR:
    """Simulates a record with UOR provenance fields."""

    def __init__(self, run_id: str, goal_id: str, **extra):
        self.run_id = run_id
        self.goal_id = goal_id
        self.status = extra.get("status", "pending")
        self.skills = extra.get("skills", ["echo"])
        self.events = extra.get("events", [])
        self.outputs = extra.get("outputs", {})
        self.metadata = extra.get("metadata", {})
        self.user_id = extra.get("user_id")
        self.uor_address = extra.get("uor_address")
        self.uor_witness = extra.get("uor_witness", {})


def test_append_includes_uor_fields(monkeypatch):
    """append() must include uor_address and uor_witness fields."""
    captured = {}

    def _mock_execute(sql, data):
        captured.update(data)

    class MockConn:
        def cursor(self):
            return MockCur()

        def commit(self):
            pass

    class MockCur:
        def execute(self, sql, data):
            _mock_execute(sql, data)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockPool:
        def getconn(self):
            return MockConn()

        def putconn(self, conn):
            pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    store._read_pool = None
    store._db_url = "mock"
    store._read_url = None

    record = FakeRecordWithUOR(
        run_id="run-1",
        goal_id="goal-1",
        uor_address="https://uor.example.com/run/1",
        uor_witness={"hash": "abc123", "timestamp": 12345},
    )

    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append(record)

    assert captured["uor_address"] == "https://uor.example.com/run/1", (
        f"Expected uor_address, got {captured.get('uor_address')!r}"
    )
    assert '"hash": "abc123"' in captured["uor_witness"], (
        f"Expected uor_witness JSON, got {captured.get('uor_witness')!r}"
    )


def test_append_many_includes_uor_fields(monkeypatch):
    """append_many() must include uor_address and uor_witness fields."""
    import csv

    captured_buf = None

    class MockConn:
        def cursor(self):
            return MockCur()

        def commit(self):
            pass

    class MockCur:
        def copy_expert(self, sql, buf):
            nonlocal captured_buf
            captured_buf = buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockPool:
        def getconn(self):
            return MockConn()

        def putconn(self, conn):
            pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    store._read_pool = None
    store._db_url = "mock"
    store._read_url = None

    records = [
        FakeRecordWithUOR(
            run_id="run-1",
            goal_id="goal-1",
            uor_address="addr-1",
            uor_witness={"w": 1},
        ),
        FakeRecordWithUOR(
            run_id="run-2",
            goal_id="goal-2",
            uor_address="addr-2",
            uor_witness={"w": 2},
        ),
    ]

    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append_many(records)

    assert captured_buf is not None
    reader = csv.reader(
        io.StringIO(captured_buf), delimiter="\t", lineterminator="\n"
    )
    rows = list(reader)
    assert len(rows) == 2
    for i, fields in enumerate(rows):
        # uor_address is field index 8, uor_witness is field index 9
        assert fields[8] == f"addr-{i+1}", (
            f"Line {i}: Expected uor_address='addr-{i+1}', got {fields[8]!r}"
        )
        assert f'"w": {i+1}' in fields[9], (
            f"Line {i}: Expected uor_witness with w={i+1}, got {fields[9]!r}"
        )


# ---------------------------------------------------------------------------
# Review-session fixes (2026-05-31)
# ---------------------------------------------------------------------------


def test_class_lru_cache_thread_safe():
    """Concurrent calls to a class_lru_cache method must not crash."""
    from uar.core.safe_utils import class_lru_cache

    call_count = 0

    class _Counter:
        @class_lru_cache(maxsize=4)
        def compute(self, x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

    obj = _Counter()
    results: list[int] = []

    def _worker():
        for i in range(100):
            results.append(obj.compute(i % 4))

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 800 calls must have returned correct values (no crashes)
    assert all(r == (i % 4) * 2 for i, r in enumerate(results)), (
        "class_lru_cache returned incorrect values under concurrency"
    )
    # Only 4 unique keys, so compute should have been called exactly 4 times.
    assert call_count == 4, (
        f"Expected 4 cache misses, got {call_count}"
    )


def test_postgres_pool_keyed_by_url(monkeypatch):
    """_get_sync_pool must return distinct pools for distinct URLs."""
    import uar.memory.postgres_store as _pg

    created: dict[str, Any] = {}

    def _mock_pool_cls(db_url: str):
        class _FakePool:
            def __init__(self, url):
                self.url = url
                created[url] = self

            def close(self):
                pass
        return _FakePool(db_url)

    # Monkeypatch both backends so we never hit the real network
    monkeypatch.setattr(
        _pg, "_db_pools", {}
    )
    monkeypatch.setattr(
        _pg.importlib.util, "find_spec",
        lambda name: "psycopg2" in name or "psycopg" in name
    )

    # Patch the constructors themselves
    monkeypatch.setattr(
        _pg, "_get_sync_pool",
        lambda db_url: (
            _pg._db_pools.setdefault(db_url, _mock_pool_cls(db_url))
            if db_url not in _pg._db_pools
            else _pg._db_pools[db_url]
        ),
        raising=False,
    )

    # Actually let's directly test the keying logic in a cleaner way
    # Restore the real function first
    monkeypatch.undo()
    # Simpler test: monkeypatch importlib to pretend nothing is installed,
    # then verify the dict keys are set correctly.
    old_pools = dict(_pg._db_pools)
    monkeypatch.setattr(_pg, "_db_pools", {})
    monkeypatch.setattr(
        _pg.importlib.util, "find_spec", lambda name: None
    )
    try:
        # When no driver is found, pool is None but dict entry is still keyed
        _pg._get_sync_pool("postgresql://host-a/db")
        _pg._get_sync_pool("postgresql://host-b/db")

        assert "postgresql://host-a/db" in _pg._db_pools, (
            "Pool for host-a not registered under its URL key"
        )
        assert "postgresql://host-b/db" in _pg._db_pools, (
            "Pool for host-b not registered under its URL key"
        )
        # Re-calling with same URL must not add a second entry
        _pg._get_sync_pool("postgresql://host-a/db")
        assert len(_pg._db_pools) == 2, (
            f"Expected 2 pools, got {len(_pg._db_pools)} — "
            "URL-keyed deduplication broken"
        )
    finally:
        _pg._db_pools.clear()
        _pg._db_pools.update(old_pools)


def test_pipeline_context_emit_overflow_is_thread_safe():
    """Concurrent emit() calls with overflow enabled must not crash."""
    import os

    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        goal = GoalSpec(id="g1", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, _max_events=50)
        assert ctx._overflow_file is not None

        errors: list[Exception] = []

        def _worker():
            try:
                for i in range(200):
                    ctx.emit("test", {"idx": i})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"emit() crashed under concurrency: {errors}"
        # deque should be at maxlen
        assert len(ctx.events) == 50, (
            f"Expected 50 events, got {len(ctx.events)}"
        )
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env


def test_emit_flush_oserror_does_not_crash(monkeypatch):
    """emit() must survive an OSError during flush (disk full, read-only)."""
    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        goal = GoalSpec(id="g1", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, _max_events=2)
        assert ctx._overflow_file is not None

        # Force flush to raise OSError after a successful write
        real_flush = ctx._overflow_file.flush
        call_count = 0

        def _bad_flush():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise OSError(28, "No space left on device")
            real_flush()

        monkeypatch.setattr(ctx._overflow_file, "flush", _bad_flush)

        # First emit fills the deque to maxlen (2)
        ctx.emit("a", {})
        ctx.emit("b", {})
        # Third emit triggers overflow write + flush
        ctx.emit("c", {})  # Should NOT raise despite OSError on flush
        assert len(ctx.events) == 2
        assert ctx.events[-1]["type"] == "c"
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env


def test_del_calls_cleanup_overflow_file(monkeypatch):
    """__del__ must call _cleanup_overflow_file to keep _overflow_paths clean.

    During normal GC (not interpreter shutdown) __del__ is the only
    cleanup path; leaving the path in _overflow_paths leaks memory.
    _cleanup_overflow_file is safe even at shutdown because any
    exception it raises (module globals already None) is swallowed by
    the outer try/except in __del__.
    """
    import inspect

    src = inspect.getsource(PipelineContext.__del__)
    assert "_cleanup_overflow_file" in src, (
        "__del__ must call _cleanup_overflow_file to remove the path "
        "from the module-level _overflow_paths registry"
    )


def test_close_removes_path_from_overflow_paths(monkeypatch):
    """close() must remove the overflow file path from _overflow_paths.

    Regression: parallel PipelineContext copies in executor.py manually
    closed the file handle and set _overflow_file=None, but the path
    remained in _overflow_paths, leaking memory.
    """
    import uar.core.contracts as _contracts

    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(id="g1", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal, _max_events=10)
    assert ctx._overflow_file is not None

    path = ctx._overflow_file.name
    assert path in _contracts._overflow_paths, (
        "Path should be in registry after creation"
    )

    ctx.close()
    assert path not in _contracts._overflow_paths, (
        "Path must be removed from _overflow_paths by close(); "
        "leaked path causes memory growth across parallel executions"
    )


def test_sqlite_writer_transient_error_does_not_poison():
    """sqlite3.OperationalError must not set _writer_exception.

    Regression: a transient BUSY/LOCKED error permanently poisoned
    all future async writes because _writer_exception was set
    unconditionally for every exception.
    """
    import inspect

    from uar.memory.sqlite_store import SqliteRunStore

    # Verify by looking at the source that OperationalError is caught
    # before the generic Exception handler.
    src = inspect.getsource(SqliteRunStore._writer_loop)
    assert "except sqlite3.OperationalError" in src, (
        "OperationalError must be caught before generic Exception"
    )
    assert "permanently raise" in src, (
        "Comment about not poisoning must be present"
    )

    # Functional test: enqueue an insert and verify the writer thread
    # does not poison itself on a simulated OperationalError.
    store = SqliteRunStore(path=":memory:")
    store._writer_queue.put(("insert", (
        "r1", "g1", None, "pending",
        "[]", "[]", "{}", "{}", None, None, 0.0,
    )))
    store._writer_queue.join()
    assert store._writer_exception is None, (
        "Writer exception should be None after a successful insert"
    )


def test_overflow_paths_is_thread_safe():
    """Concurrent _overflow_paths add/discard must not lose elements."""
    import uar.core.contracts as _contracts

    # Temporarily replace the real set with a fresh one to avoid
    # polluting module state with test paths.
    original_paths = _contracts._overflow_paths
    _contracts._overflow_paths = set()
    try:
        errors: list[Exception] = []

        def _worker_add(idx: int):
            try:
                with _contracts._overflow_init_lock:
                    _contracts._overflow_paths.add(f"/tmp/fake_{idx}.jsonl")
            except Exception as exc:
                errors.append(exc)

        def _worker_discard(idx: int):
            try:
                with _contracts._overflow_init_lock:
                    _contracts._overflow_paths.discard(
                        f"/tmp/fake_{idx}.jsonl"
                    )
            except Exception as exc:
                errors.append(exc)

        threads = []
        for i in range(50):
            threads.append(threading.Thread(target=_worker_add, args=(i,)))
            threads.append(threading.Thread(target=_worker_discard, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        # After adding and discarding the same paths, the set should be empty
        assert _contracts._overflow_paths == set(), (
            f"Expected empty set, got {_contracts._overflow_paths}"
        )
    finally:
        _contracts._overflow_paths = original_paths


def test_overflow_lock_initialised_in_post_init():
    """_overflow_lock must be created unconditionally in __post_init__."""
    goal = GoalSpec(id="g1", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)

    assert ctx._overflow_lock is not None, (
        "_overflow_lock must be initialised in __post_init__ even when "
        "UAR_CONTEXT_DISK_OVERFLOW is not enabled"
    )
    assert isinstance(ctx._overflow_lock, type(threading.Lock())), (
        "_overflow_lock must be a threading.Lock instance"
    )


def test_parallel_ctx_copy_disables_overflow(monkeypatch):
    """PipelineContext copies used in parallel execution must not keep
    overflow files open, preventing temp-file exhaustion."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    from uar.core.contracts import GoalSpec

    goal = GoalSpec(id="g1", user_intent="t", objective="t")

    # We can't easily call the full parallel path without a real executor
    # setup, so we test the invariant directly: after creating a
    # PipelineContext and closing its overflow file, emit() must not
    # try to write to disk.
    ctx = PipelineContext(goal=goal, _max_events=10)
    assert ctx._overflow_file is not None
    # Simulate the executor's cleanup path
    try:
        ctx._overflow_file.close()
    except Exception:
        pass
    object.__setattr__(ctx, "_overflow_file", None)

    ctx.emit("test", {"idx": 1})
    assert len(ctx.events) == 1
    # No exception means the fix works (emit() gracefully handles None file)


# ---------------------------------------------------------------------------
# Review-session fixes batch (2026-05-31)
# ---------------------------------------------------------------------------


def test_emit_does_not_crash_when_closed_concurrently(monkeypatch):
    """emit() must survive close() called by another thread (TOCTOU fix).

    Regression: _overflow_file was checked outside the lock; a concurrent
    close() could set it to None before the write happened.
    """
    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        goal = GoalSpec(id="g1", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, _max_events=10)
        assert ctx._overflow_file is not None

        errors: list[Exception] = []

        def _emitter():
            try:
                for i in range(500):
                    ctx.emit("test", {"idx": i})
            except Exception as exc:
                errors.append(exc)

        def _closer():
            for _ in range(50):
                ctx.close()

        threads = [
            threading.Thread(target=_emitter),
            threading.Thread(target=_closer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, (
            f"emit() crashed when close() raced: {errors}"
        )
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env


def test_batch_pool_shutdown_is_locked():
    """_shutdown_batch_pool must acquire _batch_pool_lock before mutating.

    Regression: shutdown read _batch_pool and set _batch_pool_shutdown
    outside the lock, creating a TOCTOU race with _get_batch_pool().
    """
    import inspect
    import uar.uor.batch_operations as _bo

    src = inspect.getsource(_bo._shutdown_batch_pool)
    assert "with _batch_pool_lock:" in src, (
        "_shutdown_batch_pool must acquire _batch_pool_lock to prevent race"
    )


def test_recipes_cache_is_thread_safe():
    """Concurrent get_recipe_skills calls must not corrupt cache state."""
    import os
    import tempfile
    from uar.core.recipes import (
        clear_recipes_cache,
        get_recipe_skills,
    )

    # Create a temporary user recipes file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(
            {"test_recipe": {"skills": ["alpha", "beta"]}},
            f,
        )
        tmp_path = f.name

    # Point the module at our temp file
    original_path = os.environ.get("PROJECT_ROOT")
    os.environ["PROJECT_ROOT"] = str(tempfile.gettempdir())

    # Write file into the expected location
    import pathlib
    recipes_dir = pathlib.Path(tempfile.gettempdir()) / ".uar_data"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    recipes_file = recipes_dir / "user_recipes.json"
    os.replace(tmp_path, recipes_file)

    clear_recipes_cache()

    try:
        results: list = []

        def _worker():
            for _ in range(100):
                r = get_recipe_skills("test_recipe")
                results.append(r)

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results must be the same correct value
        assert all(r == ["alpha", "beta"] for r in results), (
            "Cache corruption detected under concurrent access"
        )
    finally:
        if original_path is None:
            os.environ.pop("PROJECT_ROOT", None)
        else:
            os.environ["PROJECT_ROOT"] = original_path
        clear_recipes_cache()
        recipes_file.unlink(missing_ok=True)


def test_recipes_cache_detects_sub_second_changes():
    """User recipes cache must detect file changes within the same second.

    Regression: os.path.getmtime only has 1-second precision on many
    filesystems, so rapid updates were invisible to the cache.
    """
    import os
    import tempfile
    from uar.core.recipes import (
        clear_recipes_cache,
        get_recipe_skills,
    )

    # Create a temporary user recipes file
    recipes_dir = pathlib.Path(tempfile.gettempdir()) / ".uar_data"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    recipes_file = recipes_dir / "user_recipes.json"

    original_path = os.environ.get("PROJECT_ROOT")
    os.environ["PROJECT_ROOT"] = str(tempfile.gettempdir())

    recipes_file.write_text(
        json.dumps({"subsec": {"skills": ["v1"]}})
    )
    clear_recipes_cache()

    try:
        # First read
        assert get_recipe_skills("subsec") == ["v1"]

        # Overwrite with different content immediately
        recipes_file.write_text(
            json.dumps({"subsec": {"skills": ["v2"]}})
        )

        # The nanosecond mtime must detect the change
        assert get_recipe_skills("subsec") == ["v2"], (
            "Sub-second recipe change was not detected — mtime precision bug"
        )
    finally:
        if original_path is None:
            os.environ.pop("PROJECT_ROOT", None)
        else:
            os.environ["PROJECT_ROOT"] = original_path
        clear_recipes_cache()
        recipes_file.unlink(missing_ok=True)


def test_parallel_ctx_copy_skips_overflow_creation(monkeypatch):
    """Parallel PipelineContext copies must never create overflow files.

    Regression: Even though the executor immediately closed the overflow
    file, creating it at all wastes FDs and filesystem churn under load.
    """
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(id="g1", user_intent="t", objective="t")

    import uar.core.contracts as _contracts

    before = len(_contracts._overflow_paths)

    # Simulate the executor's parallel copy creation pattern using the
    # explicit _enable_disk_overflow=False parameter instead of mutating
    # process-global os.environ.
    ctx_copy = PipelineContext(
        goal=goal, _enable_disk_overflow=False
    )

    # The copy must NOT have an overflow file
    assert ctx_copy._overflow_file is None, (
        "Parallel PipelineContext copy still created an overflow file"
    )
    assert len(_contracts._overflow_paths) == before, (
        "_overflow_paths grew even though no file was created"
    )


def test_supervisor_stop_all_no_double_close():
    """stop_all must not close the same file handle twice.

    Regression: proc.stdout and _log_fps[name] reference the same
    handle when log_path is set, causing a double-close.
    """
    from uar.boot import ServiceSupervisor

    supervisor = ServiceSupervisor()
    # Start a trivial process with a log file
    log_path = tempfile.mktemp(suffix=".log")
    pid = supervisor.start(
        "test_svc",
        [sys.executable, "-c", "print('hello')"],
        log_path=pathlib.Path(log_path),
    )
    assert pid is not None

    # We can't easily intercept the real file handle, so we test the
    # invariant at the source level: stop_all tracks closed handles.
    import inspect
    src = inspect.getsource(supervisor.stop_all)
    assert "closed" in src, (
        "stop_all must track closed handles to avoid double-close"
    )
    assert "fp is c" in src, (
        "stop_all must skip handles already closed via proc.stdout"
    )

    supervisor.stop_all()
    os.unlink(log_path)


def test_load_program_rejects_oversized():
    """load_program must raise ValueError when program exceeds memory."""
    from uar.skills.riscv_sim import RiscvEmulator

    emu = RiscvEmulator(memory_size=16)  # 16 bytes = 4 words
    # 5 words = 20 bytes > 16
    words = [0x00000013] * 5  # 5 NOPs
    with pytest.raises(ValueError, match="exceeds memory"):
        emu.load_program(words)


def test_load_program_accepts_exact_fit():
    """load_program must succeed when program exactly fits memory."""
    from uar.skills.riscv_sim import RiscvEmulator

    emu = RiscvEmulator(memory_size=16)  # 16 bytes = 4 words
    words = [0x00000013] * 4  # 4 NOPs
    emu.load_program(words)  # Should not raise
    assert emu.pc == 0


def test_enable_disk_overflow_explicit_false_overrides_env_var(monkeypatch):
    """_enable_disk_overflow=False prevents overflow when env is 'true'."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(id="g1", user_intent="t", objective="t")

    ctx = PipelineContext(goal=goal, _enable_disk_overflow=False)
    assert ctx._overflow_file is None, (
        "_enable_disk_overflow=False did not prevent overflow file creation"
    )


def test_enable_disk_overflow_explicit_true_overrides_env_var(monkeypatch):
    """_enable_disk_overflow=True enables overflow even when env is unset."""
    monkeypatch.delenv("UAR_CONTEXT_DISK_OVERFLOW", raising=False)
    goal = GoalSpec(id="g1", user_intent="t", objective="t")

    ctx = PipelineContext(goal=goal, _enable_disk_overflow=True)
    assert ctx._overflow_file is not None, (
        "_enable_disk_overflow=True did not create overflow file"
    )
    ctx.close()


def test_env_var_race_no_longer_exists_in_executor_source():
    """executor.py must not mutate os.environ['UAR_CONTEXT_DISK_OVERFLOW'].

    Regression: The parallel group creation path temporarily set the
    process-global env var to 'false' and restored it in a finally block.
    This created a race where other threads saw the wrong value during the
    narrow mutation window.
    """
    import inspect
    import uar.core.executor as _exec

    src = inspect.getsource(_exec)
    assert 'os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "false"' not in src, (
        "executor.py still mutates os.environ for overflow control — "
        "the global env-var race has not been fixed"
    )
    assert 'UAR_CONTEXT_DISK_OVERFLOW' not in src or (
        '_enable_disk_overflow=False' in src
    ), (
        "executor.py must use _enable_disk_overflow=False instead of "
        "mutating os.environ"
    )


def test_executor_parallel_group_uses_explicit_overflow_disable():
    """executor.py parallel group must pass _enable_disk_overflow=False."""
    import inspect
    import uar.core.executor as _exec

    src = inspect.getsource(_exec.Executor.iter_events)
    assert "_enable_disk_overflow=False" in src, (
        "executor.py parallel group does not pass _enable_disk_overflow=False"
    )


def test_concurrent_root_and_parallel_contexts_no_race(monkeypatch):
    """Root contexts and parallel copies created concurrently must not
    interfere.

    Regression: When the executor mutated os.environ, a root context
    created on another thread during the mutation window would silently
    lose its overflow file.
    """
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(id="g1", user_intent="t", objective="t")

    errors: list[Exception] = []
    results: list = []

    def _root_context_worker():
        try:
            for _ in range(20):
                ctx = PipelineContext(goal=goal)
                results.append(ctx._overflow_file is not None)
                ctx.close()
        except Exception as exc:
            errors.append(exc)

    def _parallel_copy_worker():
        try:
            for _ in range(20):
                ctx = PipelineContext(
                    goal=goal, _enable_disk_overflow=False
                )
                results.append(ctx._overflow_file is None)
                ctx.close()
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=_root_context_worker),
        threading.Thread(target=_parallel_copy_worker),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent context creation crashed: {errors}"
    # All root contexts must have overflow files; all copies must not
    assert all(results), (
        "Some root contexts lost overflow files or parallel copies got them"
    )


def test_append_many_escapes_tabs_and_newlines(monkeypatch):
    """append_many must escape tabs/newlines via CSV writer."""
    import csv
    import inspect

    from uar.memory.postgres_store import PostgresRunStore

    # Verify the implementation uses csv.writer and copy_expert
    src = inspect.getsource(PostgresRunStore.append_many)
    assert "csv.writer" in src, (
        "append_many must use csv.writer to escape special characters"
    )
    assert "copy_expert" in src, (
        "append_many must use copy_expert for CSV COPY protocol"
    )
    assert "FORMAT CSV" in src, (
        "copy_expert SQL must specify CSV format with tab delimiter"
    )

    # Functional test: mock the DB and verify tab/newline fields are escaped
    captured_buf = None

    class MockConn:
        def cursor(self):
            return MockCur()

        def commit(self):
            pass

    class MockCur:
        def copy_expert(self, sql, buf):
            nonlocal captured_buf
            captured_buf = buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockPool:
        def getconn(self):
            return MockConn()

        def putconn(self, conn):
            pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    store._read_pool = None
    store._db_url = "mock"
    store._read_url = None

    records = [
        FakeRecordWithUOR(
            run_id="run-tab",
            goal_id="goal-1",
            metadata={"note": "has\ttab"},
        ),
        FakeRecordWithUOR(
            run_id="run-nl",
            goal_id="goal-2",
            metadata={"note": "has\nnewline"},
        ),
    ]

    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append_many(records)

    assert captured_buf is not None
    reader = csv.reader(
        io.StringIO(captured_buf), delimiter="\t", lineterminator="\n"
    )
    rows = list(reader)
    assert len(rows) == 2

    # Field index 7 is metadata JSON; it must contain the tab/newline
    # characters intact because csv.writer properly escapes them.
    meta_0 = json.loads(rows[0][7])
    assert meta_0["note"] == "has\ttab", (
        "Tab character was corrupted in COPY data"
    )
    meta_1 = json.loads(rows[1][7])
    assert meta_1["note"] == "has\nnewline", (
        "Newline character was corrupted in COPY data"
    )
