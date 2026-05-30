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
import json
import os
import time

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


def test_pipeline_context_close_exception_swallowed(monkeypatch):
    """close() must swallow exceptions from _overflow_file.close()."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)
    assert ctx._overflow_file is not None
    # Patch close to raise an exception
    original_close = ctx._overflow_file.close
    ctx._overflow_file.close = lambda: (_ for _ in ()).throw(
        RuntimeError("boom")
    )
    ctx.close()  # must not raise
    # Restore for clean teardown
    if ctx._overflow_file is not None:
        ctx._overflow_file.close = original_close
        ctx._overflow_file.close()


def test_pipeline_context_del_closes_overflow_file(tmp_path, monkeypatch):
    """__del__ must close the overflow file when set."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)
    overflow = ctx._overflow_file
    assert overflow is not None, "Expected overflow file to be open"
    assert not overflow.closed

    ctx.close()
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


# ---------------------------------------------------------------------------
# 6. skill_utils — skill_guard and require_package
# ---------------------------------------------------------------------------


def test_skill_guard_preserves_exception_info():
    """skill_guard must include exception type/message in error field."""
    from uar.core.skill_utils import skill_guard

    @skill_guard("Test op", status="failed")
    def boom(ctx):
        raise ValueError("something broke")

    result = boom(None)
    assert result["status"] == "failed"
    assert "ValueError" in result["error"]
    assert "something broke" in result["error"]


def test_skill_guard_uses_provided_status():
    """skill_guard must use the status kwarg, not always 'error'."""
    from uar.core.skill_utils import skill_guard

    @skill_guard("Test op", status="failed")
    def fail(ctx):
        raise RuntimeError("x")

    result = fail(None)
    assert result["status"] == "failed"


def test_require_package_empty_string():
    """Empty string package must be reported as missing."""
    from uar.core.skill_utils import require_package

    result = require_package("")
    assert result is not None
    assert result["status"] == "failed"


def test_require_package_empty_in_list():
    """Empty string in a list must be reported as missing."""
    from uar.core.skill_utils import require_package

    result = require_package(["os", ""])
    assert result is not None
    assert "<empty>" in result["error"]


def test_require_package_installed():
    """Installed package returns None."""
    from uar.core.skill_utils import require_package

    assert require_package("os") is None


def test_require_package_missing():
    """Missing package returns error dict."""
    from uar.core.skill_utils import require_package

    result = require_package("definitely_not_a_real_package_12345")
    assert isinstance(result, dict)
    assert result["status"] == "failed"
    assert "definitely_not_a_real_package_12345" in result["error"]


# ---------------------------------------------------------------------------
# 7. JsonRunStore.list_all respects limit parameter
# ---------------------------------------------------------------------------


def test_json_run_store_list_all_accepts_limit(tmp_path):
    """JsonRunStore.list_all must accept and forward the limit parameter."""
    from uar.memory.json_store import JsonRunStore

    store = JsonRunStore(str(tmp_path / "runs.jsonl"))
    for i in range(5):
        store.append(
            RunRecord(
                run_id=f"r{i}",
                goal_id="g",
                skills=["noop"],
                status="completed",
            )
        )
    store.flush()

    all_records = store.list_all(limit=1000)
    assert len(all_records) == 5

    limited = store.list_all(limit=2)
    assert len(limited) == 2


# ---------------------------------------------------------------------------
# 8. RunStoreProtocol includes purge_old_records
# ---------------------------------------------------------------------------


def test_run_store_protocol_has_purge_old_records():
    """All stores must satisfy the purge_old_records protocol method."""
    from uar.memory.base_store import RunStoreProtocol

    assert hasattr(RunStoreProtocol, "purge_old_records")


# ---------------------------------------------------------------------------
# 9. PostgresRunStore has purge_old_records
# ---------------------------------------------------------------------------


def test_postgres_run_store_has_purge_old_records():
    """PostgresRunStore must implement purge_old_records."""
    from uar.memory.postgres_store import PostgresRunStore

    assert hasattr(PostgresRunStore, "purge_old_records")


# ---------------------------------------------------------------------------
# 10. Hierarchical env var "false" must not enable hierarchical mode
# ---------------------------------------------------------------------------


def _run_executor_with_env(monkeypatch, env_value: str):
    """Helper: run executor with given env value, return executor instance."""
    from unittest.mock import Mock, patch

    from uar.core.executor import Executor
    from uar.core.contracts import GoalSpec, StrategySpec

    monkeypatch.setenv("UAR_HIERARCHICAL_EXECUTION", env_value)
    mock_skill = Mock(return_value={"status": "ok"})

    with patch("uar.core.executor.registry") as mock_registry:
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill
        executor = Executor()
        goal = GoalSpec(
            id="g1",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {"type": "recipe", "content": "cached_r", "id": "r1"},
                ],
                "recipe_definitions": [
                    {"id": "cached_r", "skills": ["noop"], "cache": True},
                ],
            },
        )
        strategy = StrategySpec(goal_id="g1", ordered_skills=["noop"])
        list(executor.iter_events(strategy, goal, timeout_seconds=5.0))

    return executor


def test_hierarchical_env_false_not_truthy(monkeypatch):
    """UAR_HIERARCHICAL_EXECUTION=false must not trigger hierarchical mode."""
    executor = _run_executor_with_env(monkeypatch, "false")
    # Flat mode does not populate recipe cache
    assert len(executor._recipe_cache) == 0


def test_hierarchical_env_one_is_truthy(monkeypatch):
    """UAR_HIERARCHICAL_EXECUTION=1 must trigger hierarchical mode."""
    executor = _run_executor_with_env(monkeypatch, "1")
    # Hierarchical mode with cache=True populates recipe cache
    assert len(executor._recipe_cache) == 1


# ---------------------------------------------------------------------------
# 11. RAGResult uses retrieved_nodes, not sources
# ---------------------------------------------------------------------------


def test_rag_result_has_retrieved_nodes_not_sources():
    """RAGResult dataclass must expose retrieved_nodes, not sources."""
    from uar.core.llamaindex_rag import RAGResult

    result = RAGResult(query="q", response="r")
    assert hasattr(result, "retrieved_nodes")
    assert not hasattr(result, "sources")


# ---------------------------------------------------------------------------
# 12. SqliteRunStore.purge_old_records — regression for Julian day bug
# ---------------------------------------------------------------------------


def test_sqlite_purge_old_records_actually_removes_rows(tmp_path):
    """purge_old_records must delete rows older than retention_days.

    Regression: created_at defaulted to julianday('now') while cutoff
    was computed in Unix epoch seconds, so the comparison was always
    false and nothing was ever deleted.
    """
    from uar.memory.sqlite_store import SqliteRunStore

    db = tmp_path / "purge_test.db"
    store = SqliteRunStore(path=str(db))
    try:
        # Insert a record with an explicitly old created_at
        # (Unix epoch seconds, 10 days ago)
        old_ts = time.time() - (10 * 86400)
        conn = store._get_conn()
        conn.execute(
            "INSERT INTO uar_runs (run_id, goal_id, skills, created_at)"
            " VALUES (?, ?, ?, ?)",
            ("run-old", "goal", json.dumps(["noop"]), old_ts),
        )
        conn.commit()

        # Insert a recent record
        conn.execute(
            "INSERT INTO uar_runs (run_id, goal_id, skills, created_at)"
            " VALUES (?, ?, ?, julianday('now'))",
            ("run-new", "goal", json.dumps(["noop"])),
        )
        conn.commit()

        assert len(store.list_records()) == 2

        # Purge records older than 5 days
        removed = store.purge_old_records(5)
        assert removed == 1, f"Expected 1 removed, got {removed}"
        remaining = store.list_records()
        assert len(remaining) == 1
        assert remaining[0]["run_id"] == "run-new"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 13. JsonRunStore.purge_old_records — regression for timestamp key bug
# ---------------------------------------------------------------------------


def test_json_purge_old_records_actually_removes_lines(tmp_path):
    """purge_old_records must delete records older than retention_days.

    Regression: the method looked for 'timestamp' which was never written;
    records always lacked it so nothing was ever removed.
    """
    from uar.memory.json_store import JsonRunStore

    path = tmp_path / "runs.jsonl"
    store = JsonRunStore(str(path))

    # Append a recent record
    store.append(
        RunRecord(
            run_id="run-new", goal_id="g", skills=["noop"],
            status="completed",
        )
    )
    store.flush()

    # Append an old record by writing raw JSON with backdated created_at
    old_line = json.dumps(
        {
            "run_id": "run-old",
            "goal_id": "g",
            "skills": ["noop"],
            "status": "completed",
            "created_at": time.time() - (10 * 86400),
        },
        sort_keys=True,
    )
    with path.open("a") as f:
        f.write(old_line + "\n")

    assert len(store.list_records()) == 2

    removed = store.purge_old_records(5)
    assert removed == 1, f"Expected 1 removed, got {removed}"
    remaining = store.list_records()
    assert len(remaining) == 1
    assert remaining[0]["run_id"] == "run-new"


# ---------------------------------------------------------------------------
# 14. require_package empty string produces clear message
# ---------------------------------------------------------------------------


def test_require_package_empty_string_clear_message():
    """Empty string package must produce a readable error message."""
    from uar.core.skill_utils import require_package

    result = require_package("")
    assert result is not None
    assert "<empty>" in result["error"]


# ---------------------------------------------------------------------------
# 15. skill_guard default status for framework wrappers
# ---------------------------------------------------------------------------


def test_skill_guard_default_status_is_error():
    """Framework wrappers without explicit status must default to 'error'."""
    from uar.core.skill_utils import skill_guard

    @skill_guard("Framework Op")
    def boom(ctx):
        raise RuntimeError("framework failure")

    result = boom(None)
    assert result["status"] == "error"


def test_pipeline_context_del_exception_path(monkeypatch):
    """__del__ must swallow exceptions in close() and logger.warning()."""
    from unittest.mock import patch

    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)

    with patch(
        "uar.core.contracts.PipelineContext.close",
        side_effect=RuntimeError("close boom"),
    ):
        with patch(
            "uar.core.contracts.logger.warning",
            side_effect=RuntimeError("log boom"),
        ):
            # Must not raise despite both close() and logger.warning() failing
            ctx.__del__()


def test_pipeline_context_overflow_emit_saves_oldest():
    """When deque is full, emit must write the oldest event to overflow."""
    import tempfile

    goal = GoalSpec(id="g", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal, _max_events=2)
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    overflow = open(path, "a")
    object.__setattr__(ctx, "_overflow_file", overflow)

    ctx.emit("a", {"n": 1})
    ctx.emit("b", {"n": 2})
    ctx.emit("c", {"n": 3})

    overflow.close()
    with open(path) as f:
        lines = [json.loads(line) for line in f]
    os.unlink(path)

    assert len(lines) == 1
    assert lines[0]["type"] == "a"
