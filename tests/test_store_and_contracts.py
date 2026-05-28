"""Regression tests for store field mapping, PipelineContext,
async_utils, and safe_eval.

Covers:
  - PostgresRunStore / SqliteRunStore field-mapping bug (run_id, goal_id)
  - PipelineContext deque-based O(1) event eviction
  - PipelineContext overflow-file __del__ cleanup
  - run_record_from_dict key-filtering
  - run_sync_safe coroutine runner (no-loop and running-loop paths)
  - safe_eval subscript slice security (concatenated dunder bypass)
"""
import asyncio
import collections
import os

import pytest

from uar.core.contracts import GoalSpec, PipelineContext, RunRecord
from uar.core.async_utils import run_sync_safe
from uar.memory.base_store import run_record_from_dict


# ---------------------------------------------------------------------------
# 1. run_record_from_dict — extra keys must be filtered
# ---------------------------------------------------------------------------


def test_run_record_from_dict_filters_and_instantiates():
    row = {
        "run_id": "r1",
        "goal_id": "g1",
        "skills": ["foo"],
        "status": "completed",
        "created_at": "2025-01-01",   # Postgres-only column
        "id": 42,                      # Postgres serial PK
        "metadata": {"x": 1},         # now a RunRecord field
    }
    rr = run_record_from_dict(row)
    assert rr.run_id == "r1"
    assert rr.goal_id == "g1"
    assert rr.skills == ["foo"]
    assert rr.status == "completed"
    assert rr.metadata == {"x": 1}


def test_run_record_from_dict_missing_required_raises():
    with pytest.raises(TypeError):
        run_record_from_dict({"run_id": "r1"})  # goal_id + skills missing


# ---------------------------------------------------------------------------
# 2. Store field mapping — SqliteRunStore must store run_id / goal_id
# ---------------------------------------------------------------------------


def test_sqlite_store_append_field_mapping(tmp_path):
    """SqliteRunStore.append must persist run_id and goal_id correctly."""
    from uar.memory.sqlite_store import SqliteRunStore

    db = tmp_path / "test.db"
    store = SqliteRunStore(path=str(db))
    try:
        record = RunRecord(
            run_id="run-abc",
            goal_id="goal-xyz",
            skills=["noop"],
            status="completed",
        )
        store.append(record)
        store.flush()

        rows = store.list_records()
        assert len(rows) == 1
        assert rows[0]["run_id"] == "run-abc", (
            f"run_id mismatch: {rows[0]['run_id']!r}"
        )
        assert rows[0]["goal_id"] == "goal-xyz", (
            f"goal_id mismatch: {rows[0]['goal_id']!r}"
        )
    finally:
        store.close()


def test_sqlite_store_append_many_field_mapping(tmp_path):
    """SqliteRunStore.append_many must persist run_id and goal_id correctly."""
    from uar.memory.sqlite_store import SqliteRunStore

    db = tmp_path / "test_many.db"
    store = SqliteRunStore(path=str(db))
    try:
        records = [
            RunRecord(
                run_id=f"run-{i}",
                goal_id=f"goal-{i}",
                skills=["noop"],
            )
            for i in range(3)
        ]
        store.append_many(records)
        store.flush()

        rows = store.list_records()
        assert len(rows) == 3
        run_ids = {r["run_id"] for r in rows}
        goal_ids = {r["goal_id"] for r in rows}
        assert run_ids == {"run-0", "run-1", "run-2"}, (
            f"run_id set mismatch: {run_ids}"
        )
        assert goal_ids == {"goal-0", "goal-1", "goal-2"}, (
            f"goal_id set mismatch: {goal_ids}"
        )
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 3. PipelineContext — deque-based O(1) eviction
# ---------------------------------------------------------------------------


def test_pipeline_context_events_is_deque():
    """events must be a deque after __post_init__, not a plain list."""
    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)
    assert isinstance(ctx.events, collections.deque), (
        f"Expected deque, got {type(ctx.events)}"
    )
    assert ctx.events.maxlen == ctx._max_events


def test_pipeline_context_event_eviction_o1():
    """Filling past maxlen must evict oldest events without O(n) pop(0)."""
    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal, _max_events=3)

    for i in range(5):
        ctx.emit("test", {"i": i})

    # Only the 3 newest events should remain
    assert len(ctx.events) == 3
    evicted = list(ctx.events)
    assert evicted[0]["payload"]["i"] == 2  # oldest kept
    assert evicted[-1]["payload"]["i"] == 4  # newest


def test_pipeline_context_close_idempotent():
    """close() must be safe to call multiple times."""
    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)
    ctx.close()
    ctx.close()  # must not raise


def test_pipeline_context_del_closes_overflow_file(tmp_path, monkeypatch):
    """__del__ must close the overflow file when set."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)
    overflow = ctx._overflow_file
    assert overflow is not None, "Expected overflow file to be open"
    assert not overflow.closed

    ctx.__del__()
    assert overflow.closed


# ---------------------------------------------------------------------------
# 4. run_sync_safe — both paths (no loop and running loop)
# ---------------------------------------------------------------------------


async def _coro_add(a, b):
    await asyncio.sleep(0)
    return a + b


def test_run_sync_safe_no_loop():
    """Must work when called with no running event loop."""
    result = run_sync_safe(_coro_add(3, 4))
    assert result == 7


def test_run_sync_safe_from_running_loop():
    """Must work when called from inside a running event loop (thread path)."""

    async def _inner():
        loop = asyncio.get_running_loop()
        assert loop.is_running()
        return run_sync_safe(_coro_add(10, 20))

    result = asyncio.run(_inner())
    assert result == 30


def test_run_sync_safe_closes_coro_on_exception():
    """Coroutine must be closed (no ResourceWarning) even when it raises."""

    async def _bad():
        await asyncio.sleep(0)
        raise ValueError("intentional")

    with pytest.raises(ValueError, match="intentional"):
        run_sync_safe(_bad())


# ---------------------------------------------------------------------------
# 5. safe_eval — subscript slice security
# ---------------------------------------------------------------------------


def test_safe_eval_rejects_concatenated_dunder_subscript():
    """String concatenation in subscript slices must be rejected."""
    from uar.core.safe_eval import SafeEvalAttrError, safe_eval

    with pytest.raises(SafeEvalAttrError, match="Disallowed subscript"):
        safe_eval('obj["__" + "class__"]', {"obj": object()})


def test_safe_eval_allows_numeric_subscript():
    """Numeric subscripts like x[1 + 2] should still work."""
    from uar.core.safe_eval import safe_eval

    result = safe_eval("x[1 + 2]", {"x": [10, 20, 30, 40]})
    assert result == 40


def test_safe_eval_allows_simple_string_subscript():
    """Simple string subscripts on allowed keys should still work."""
    from uar.core.safe_eval import safe_eval

    result = safe_eval('d["foo"]', {"d": {"foo": "bar"}})
    assert result == "bar"


def test_pipeline_context_overflow_writes_oldest_event():
    """When deque is at capacity, overflow must persist the oldest event,
    not the newest one."""
    import tempfile
    import json

    ctx = PipelineContext(
        goal=GoalSpec(
            id="g1", user_intent="test", objective="test"
        ),
        _max_events=2,
    )
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    overflow = open(path, "a")
    object.__setattr__(ctx, "_overflow_file", overflow)

    ctx.emit("event_a", {"n": 1})
    ctx.emit("event_b", {"n": 2})
    # deque is now at capacity; next emit should overflow oldest
    ctx.emit("event_c", {"n": 3})

    overflow.close()
    with open(path) as f:
        lines = [json.loads(line) for line in f]
    os.unlink(path)

    assert len(lines) == 1
    assert lines[0]["type"] == "event_a"
    # In-memory deque should have the two newest events
    assert [e["type"] for e in ctx.events] == ["event_b", "event_c"]
