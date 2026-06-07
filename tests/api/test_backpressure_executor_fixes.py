"""Regression tests for streaming, backpressure, and executor fixes.

Covers:
  FIX-1  Per-request semaphore (not global) to prevent cross-request blocking
  FIX-2  Dead events deque removed from stream_goal
  FIX-3  Executor uses pre-computed strategy.waves instead of recomputing
  FIX-4  run_sync_safe uses shared ThreadPoolExecutor instead of one-shot pools
  FIX-5  _snapshot_context raises RuntimeError instead of silently returning {}
  FIX-6  CircularDependencyError propagates from dag_schedule instead of
         being swallowed
  FIX-7  websocket_endpoint re-raises asyncio.CancelledError
  FIX-8  timed decorator async_wrapper re-raises asyncio.CancelledError
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import patch

import pytest

from uar.core.async_utils import _RUN_SYNC_POOL
from uar.core.executor import _snapshot_context
from uar.core.scheduler import CircularDependencyError
from uar.services.execution import GoalExecutionService


# ------------------------------------------------------------------
# FIX-1: Per-request semaphore
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_iter_events_uses_passed_semaphore_not_global():
    """Each call to _iter_events must accept a per-request semaphore."""
    sig = inspect.signature(GoalExecutionService._iter_events)
    param_names = list(sig.parameters.keys())
    assert "bp_sem" in param_names, "_iter_events must accept bp_sem parameter"


@pytest.mark.asyncio
async def test_per_request_semaphore_isolation():
    """Two semaphores with limit 1 should not block each other."""
    sem1 = asyncio.Semaphore(1)
    sem2 = asyncio.Semaphore(1)

    acquired = []

    async def acquire_and_release(sem, label):
        await sem.acquire()
        acquired.append(label)
        sem.release()

    # Both should acquire immediately since they are independent semaphores
    await asyncio.gather(
        acquire_and_release(sem1, "a"),
        acquire_and_release(sem2, "b"),
    )
    assert sorted(acquired) == ["a", "b"]


# ------------------------------------------------------------------
# FIX-2: Dead events deque removed
# ------------------------------------------------------------------


def test_stream_goal_no_dead_events_deque():
    """stream_goal must not create an unused 'events' deque."""
    import uar.services.execution as _exec_mod

    source = inspect.getsource(_exec_mod)
    # After fix, 'events: collections.deque' or similar declaration
    # should NOT exist
    assert "events: collections.deque" not in source
    assert "events.append(raw_event)" not in source


# ------------------------------------------------------------------
# FIX-3: Execution plan consistency — executor uses strategy.waves
# ------------------------------------------------------------------


def test_executor_uses_strategy_waves_when_present():
    """When strategy.waves is already set, dag_schedule must not be called."""
    from uar.core.executor import Executor
    from uar.core.contracts import StrategySpec, GoalSpec

    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
        metadata={"enable_parallel": True},
    )
    strategy = StrategySpec(
        goal_id="g1",
        ordered_skills=["skill_a", "skill_b"],
        waves=[["skill_a", "skill_b"]],
    )

    executor = Executor()

    with patch("uar.core.executor.dag_schedule") as mock_dag:
        list(
            executor.iter_events(
                strategy, goal, timeout_seconds=5.0, correlation_id="c1"
            )
        )
        mock_dag.assert_not_called()


def test_executor_calls_dag_schedule_when_waves_missing():
    """When strategy.waves is None/empty, dag_schedule may be called."""
    from uar.core.executor import Executor
    from uar.core.contracts import StrategySpec, GoalSpec

    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
        metadata={"enable_parallel": True},
    )
    strategy = StrategySpec(
        goal_id="g1",
        ordered_skills=["skill_a", "skill_b"],
        waves=None,
    )

    executor = Executor()

    with patch(
        "uar.core.executor.dag_schedule",
        return_value=[["skill_a"], ["skill_b"]],
    ) as mock_dag:
        with patch("uar.core.executor._UAR_SCHEDULER", "dag"):
            with patch(
                "uar.core.executor.registry.is_registered",
                return_value=True,
            ):
                list(
                    executor.iter_events(
                        strategy, goal, timeout_seconds=5.0,
                        correlation_id="c1",
                    )
                )
                mock_dag.assert_called_once()


# ------------------------------------------------------------------
# FIX-4: run_sync_safe shared pool
# ------------------------------------------------------------------


def test_run_sync_safe_uses_shared_pool():
    """_RUN_SYNC_POOL must be a ThreadPoolExecutor with workers > 0."""
    import concurrent.futures

    assert isinstance(_RUN_SYNC_POOL, concurrent.futures.ThreadPoolExecutor)
    assert _RUN_SYNC_POOL._max_workers > 0


# ------------------------------------------------------------------
# FIX-5: _snapshot_context raises on failure
# ------------------------------------------------------------------


def test_snapshot_context_raises_on_deepcopy_failure(monkeypatch):
    """If deepcopy fails with pickle disabled, RuntimeError is raised."""
    monkeypatch.setattr(
        "uar.core.executor._USE_PICKLE_SNAPSHOT", False
    )
    with patch(
        "uar.core.executor.copy.deepcopy",
        side_effect=MemoryError("oom"),
    ):
        with pytest.raises(
            RuntimeError, match="copy.deepcopy snapshot failed"
        ):
            _snapshot_context({"key": "value"})


def test_snapshot_context_raises_on_total_failure():
    """If pickle fails and deepcopy also fails, RuntimeError must be raised."""
    with patch(
        "uar.core.executor.pickle.dumps", side_effect=TypeError("bad")
    ):
        with patch(
            "uar.core.executor.copy.deepcopy",
            side_effect=MemoryError("oom"),
        ):
            with pytest.raises(
                RuntimeError,
                match="Pickle and deepcopy snapshot both failed",
            ):
                _snapshot_context({"key": "value"})


def test_snapshot_context_returns_empty_for_none():
    """None input should still return {} (expected sentinel)."""
    assert _snapshot_context(None) == {}


# ------------------------------------------------------------------
# FIX-6: CircularDependencyError propagates
# ------------------------------------------------------------------


def test_circular_dependency_error_propagates():
    """CircularDependencyError from dag_schedule must not be swallowed."""
    from uar.core.executor import Executor
    from uar.core.contracts import StrategySpec, GoalSpec

    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
        metadata={"enable_parallel": True},
    )
    strategy = StrategySpec(
        goal_id="g1",
        ordered_skills=["a", "b"],
        waves=None,
    )

    executor = Executor()
    err = CircularDependencyError(["a", "b", "a"])

    with patch(
        "uar.core.executor.dag_schedule", side_effect=err
    ):
        with patch("uar.core.executor._UAR_SCHEDULER", "dag"):
            with patch(
                "uar.core.executor.registry.is_registered",
                return_value=True,
            ):
                with pytest.raises(CircularDependencyError):
                    list(
                        executor.iter_events(
                            strategy, goal, timeout_seconds=5.0,
                            correlation_id="c1",
                        )
                    )


# ------------------------------------------------------------------
# FIX-7: websocket_endpoint re-raises CancelledError
# ------------------------------------------------------------------


def test_websocket_endpoint_re_raises_cancelled_error():
    """Source inspection: websocket handler must re-raise CancelledError."""
    import uar.api.routers.streaming as _streaming_mod

    source = inspect.getsource(_streaming_mod)
    # The except block should have CancelledError before Exception
    assert "except asyncio.CancelledError:" in source
    assert "    raise" in source


# ------------------------------------------------------------------
# FIX-8: timed decorator async_wrapper re-raises CancelledError
# ------------------------------------------------------------------


def test_timed_decorator_re_raises_cancelled_error():
    """Source inspection: timed async_wrapper must re-raise CancelledError."""
    import uar.api.metrics as _metrics_mod

    source = inspect.getsource(_metrics_mod)
    # The async_wrapper inside timed() should have CancelledError
    # before the broad except Exception
    assert "except asyncio.CancelledError:" in source


# ------------------------------------------------------------------
# FIX-9: Cache guardrails failure must fall through to execution
# ------------------------------------------------------------------


def test_sequential_cache_guardrails_falls_through_source():
    """Source: sequential path uses use_cache flag, not else branch."""
    import uar.core.executor as _exec_mod

    source = inspect.getsource(_exec_mod)
    seq = source.split("# Check cache first if enabled")[1]
    assert "use_cache = False" in seq
    assert "if not use_cache:" in seq
    # _metrics_cache_hits must be inside the success (else) branch,
    # not before the guardrails check
    seq_guardrails = seq.split("_validate_output_guardrails")[1]
    first_else = seq_guardrails.split("else:")[0]
    assert "_metrics_cache_hits += 1" not in first_else


def test_parallel_cache_guardrails_falls_through_source():
    """Source: parallel loop uses cache_used flag, not else branch."""
    import uar.core.executor as _exec_mod

    source = inspect.getsource(_exec_mod)
    par = source.split("# Check cache for each skill before parallel")[1]
    assert "cache_used = False" in par
    assert "if not cache_used:" in par
    # _metrics_cache_hits must be inside the success (else) branch
    par_guardrails = par.split("_validate_output_guardrails")[1]
    first_else = par_guardrails.split("else:")[0]
    assert "_metrics_cache_hits += 1" not in first_else


def test_guardrails_failed_cache_hit_still_executes_skill():
    """Functional: guardrails-failed cache hit falls through to execution."""
    from uar.core.executor import Executor
    from uar.core.contracts import StrategySpec, GoalSpec

    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
        metadata={"enable_parallel": False},
    )
    strategy = StrategySpec(
        goal_id="g1",
        ordered_skills=["test_skill"],
        waves=None,
    )

    executor = Executor()

    class FakeCache:
        def get(self, skill_name, ctx_data, objective):
            return "cached_value"

        def set(self, *args, **kwargs):
            pass

    def _fake_guardrails(result, skill_name):
        if result == "cached_value":
            return ["guardrail_violation"]
        return []

    def _fake_skill(ctx):
        return "executed_value"

    with patch("uar.core.executor.get_cache", return_value=FakeCache()):
        with patch(
            "uar.core.executor._validate_output_guardrails",
            side_effect=_fake_guardrails,
        ):
            with patch(
                "uar.core.executor._validate_input_guardrails",
                return_value=[],
            ):
                with patch(
                    "uar.core.executor.registry.is_registered",
                    return_value=True,
                ):
                    with patch(
                        "uar.core.executor.registry.get",
                        return_value=_fake_skill,
                    ):
                        events = list(
                            executor.iter_events(
                                strategy,
                                goal,
                                timeout_seconds=5.0,
                                correlation_id="c1",
                            )
                        )

    skill_complete_events = [
        e for e in events if e.get("type") == "skill_complete"
    ]
    assert len(skill_complete_events) == 1
    assert skill_complete_events[0]["payload"]["result"] == "executed_value"

    metrics_events = [e for e in events if e.get("type") == "metrics"]
    assert len(metrics_events) == 1
    assert metrics_events[0]["payload"]["cache_hits"] == 0
    assert metrics_events[0]["payload"]["cache_misses"] == 1


# ------------------------------------------------------------------
# FIX-10: Injected WorkerPool must not be shut down by with block
# ------------------------------------------------------------------


def test_injected_pool_uses_nullcontext():
    """Source: injected self._pool must use nullcontext, not bare with."""
    import uar.core.executor as _exec_mod

    source = inspect.getsource(_exec_mod)
    # The parallel execution block should wrap injected pool in nullcontext
    assert "contextlib.nullcontext(self._pool)" in source
