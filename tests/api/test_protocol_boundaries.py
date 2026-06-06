"""Tests for T5 — Protocol Boundaries (API to Executor contract).

Covers:
- ExecutionGateway.execute returns a RunRecord
- Idempotency read-through works
- Idempotency write-back works
- Side effects (analytics cache invalidation, sync monitor) are triggered
- ValidationError propagates through the gateway
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from uar.api.gateway import ExecutionGateway
from uar.api.models import RunRequest
from uar.core.contracts import RunRecord
from uar.core.exceptions import ValidationError


def _make_req(**kwargs) -> RunRequest:
    defaults = {"goal": "test goal"}
    defaults.update(kwargs)
    return RunRequest(**defaults)


def test_gateway_execute_returns_runrecord(monkeypatch):
    """Gateway.execute returns a RunRecord with user_id set."""
    fake_record = RunRecord(
        run_id="r1",
        goal_id="g1",
        skills=["echo"],
        status="completed",
        events=[],
        outputs={},
        metadata={},
    )

    monkeypatch.setattr(
        "uar.api.gateway._build_goal",
        lambda req: MagicMock(id="g1", user_intent=req.goal,
                              objective=req.goal, required_skills=[],
                              metadata={}, constraints=[],
                              success_criteria=[]),
    )
    monkeypatch.setattr(
        "uar.core.planner.SimplePlanner",
        MagicMock(return_value=MagicMock(
            plan=lambda goal: MagicMock(goal_id="g1", ordered_skills=["echo"])
        )),
    )
    monkeypatch.setattr(
        "uar.core.executor.Executor",
        MagicMock(return_value=MagicMock(
            run=lambda strategy, goal, timeout_seconds: fake_record
        )),
    )

    store = MagicMock()
    gateway = ExecutionGateway(store=store)
    result = gateway.execute(_make_req(), user_id="alice")

    assert result is fake_record
    assert result.user_id == "alice"
    store.append.assert_called_once_with(fake_record)


def test_gateway_idempotency_read_through(monkeypatch):
    """If idempotency_get returns a cached record, execute returns it."""
    cached = RunRecord(
        run_id="cached",
        goal_id="g1",
        skills=["echo"],
        status="completed",
        events=[],
        outputs={},
        metadata={},
    )
    idempotency_get = MagicMock(return_value=cached)

    gateway = ExecutionGateway(idempotency_get=idempotency_get)
    req = _make_req(idempotency_key="key-123")
    result = gateway.execute(req)

    assert result is cached
    idempotency_get.assert_called_once_with("key-123")


def test_gateway_idempotency_write_back(monkeypatch):
    """After successful execution, result is cached via idempotency_set."""
    fake_record = RunRecord(
        run_id="r1",
        goal_id="g1",
        skills=["echo"],
        status="completed",
        events=[],
        outputs={},
        metadata={},
    )

    monkeypatch.setattr(
        "uar.api.gateway._build_goal",
        lambda req: MagicMock(id="g1", user_intent=req.goal,
                              objective=req.goal, required_skills=[],
                              metadata={}, constraints=[],
                              success_criteria=[]),
    )
    monkeypatch.setattr(
        "uar.core.planner.SimplePlanner",
        MagicMock(return_value=MagicMock(
            plan=lambda goal: MagicMock(goal_id="g1", ordered_skills=["echo"])
        )),
    )
    monkeypatch.setattr(
        "uar.core.executor.Executor",
        MagicMock(return_value=MagicMock(
            run=lambda strategy, goal, timeout_seconds: fake_record
        )),
    )

    idempotency_set = MagicMock()
    gateway = ExecutionGateway(
        store=MagicMock(),
        idempotency_set=idempotency_set,
    )
    req = _make_req(idempotency_key="key-456")
    gateway.execute(req)

    idempotency_set.assert_called_once_with("key-456", fake_record)


def test_gateway_side_effects(monkeypatch):
    """Analytics cache is invalidated and sync monitor is notified."""
    fake_record = RunRecord(
        run_id="r1",
        goal_id="g1",
        skills=["echo"],
        status="completed",
        events=[],
        outputs={},
        metadata={},
    )

    monkeypatch.setattr(
        "uar.api.gateway._build_goal",
        lambda req: MagicMock(id="g1", user_intent=req.goal,
                              objective=req.goal, required_skills=[],
                              metadata={}, constraints=[],
                              success_criteria=[]),
    )
    monkeypatch.setattr(
        "uar.core.planner.SimplePlanner",
        MagicMock(return_value=MagicMock(
            plan=lambda goal: MagicMock(goal_id="g1", ordered_skills=["echo"])
        )),
    )
    monkeypatch.setattr(
        "uar.core.executor.Executor",
        MagicMock(return_value=MagicMock(
            run=lambda strategy, goal, timeout_seconds: fake_record
        )),
    )

    analytics_cache = MagicMock()
    sync_monitor = MagicMock()
    gateway = ExecutionGateway(
        store=MagicMock(),
        analytics_cache=analytics_cache,
        sync_monitor=sync_monitor,
    )
    gateway.execute(_make_req())

    analytics_cache.invalidate.assert_called_once()
    sync_monitor.record_write.assert_called_once_with("default")


def test_gateway_validation_error_propagates(monkeypatch):
    """ValidationError from _build_goal propagates through the gateway."""
    def _failing_build_goal(req):
        raise ValidationError("bad input", field="goal")

    monkeypatch.setattr(
        "uar.api.gateway._build_goal", _failing_build_goal
    )

    gateway = ExecutionGateway()
    with pytest.raises(ValidationError, match="bad input"):
        gateway.execute(_make_req())
