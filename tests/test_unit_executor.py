"""Unit tests for executor module"""

import pytest
import time
from unittest.mock import Mock, patch

from uar.core.executor import (
    get_max_retries,
    _run_with_timeout,
    _event,
    Executor,
)
from uar.core.exceptions import TimeoutError, ValidationError
from uar.core.contracts import StrategySpec, GoalSpec, PipelineContext


class TestGetMaxRetries:
    """Test get_max_retries function"""

    def test_default_retry_policy(self):
        """Default retry policy returns configured default"""
        result = get_max_retries("unknown_skill")
        assert result >= 0

    def test_ollama_retry_policy(self):
        """Ollama skill has specific retry policy"""
        result = get_max_retries("ollama_generate")
        assert result == 3

    def test_graphrag_retry_policy(self):
        """GraphRAG skill has specific retry policy"""
        result = get_max_retries("graphrag_query")
        assert result == 2

    def test_autonomi_upload_retry_policy(self):
        """Autonomi upload has specific retry policy"""
        result = get_max_retries("autonomi_upload")
        assert result == 3

    def test_autonomi_download_retry_policy(self):
        """Autonomi download has specific retry policy"""
        result = get_max_retries("autonomi_download")
        assert result == 3


class TestRunWithTimeout:
    """Test _run_with_timeout function"""

    def test_successful_execution(self):
        """Function that completes successfully returns result"""

        def successful_fn(ctx):
            return "success"

        goal = GoalSpec(id="test", user_intent="test", objective="test")
        ctx = PipelineContext(goal=goal)
        result = _run_with_timeout(successful_fn, ctx, timeout_seconds=1.0)
        assert result == "success"

    def test_timeout_raises_error(self):
        """Function that times out raises TimeoutError"""

        def slow_fn(ctx):
            time.sleep(2.0)
            return "should not reach here"

        goal = GoalSpec(id="test", user_intent="test", objective="test")
        ctx = PipelineContext(goal=goal)
        with pytest.raises(TimeoutError):
            _run_with_timeout(slow_fn, ctx, timeout_seconds=0.1)

    def test_exception_propagates(self):
        """Function that raises exception propagates the exception"""

        def failing_fn(ctx):
            raise ValueError("test error")

        goal = GoalSpec(id="test", user_intent="test", objective="test")
        ctx = PipelineContext(goal=goal)
        with pytest.raises(ValueError):
            _run_with_timeout(failing_fn, ctx, timeout_seconds=1.0)


class TestEventFunction:
    """Test _event function"""

    def test_event_structure(self):
        """Event has correct structure"""
        event = _event(
            "test_type",
            "run_123",
            "goal_456",
            skill="test_skill",
            payload={"key": "value"},
            error="test_error",
            correlation_id="corr_789",
        )

        assert event["schema_version"] == "uar.event.v1"
        assert event["type"] == "test_type"
        assert event["run_id"] == "run_123"
        assert event["goal_id"] == "goal_456"
        assert event["skill"] == "test_skill"
        assert event["payload"] == {"key": "value"}
        assert event["error"] == "test_error"
        assert event["correlation_id"] == "corr_789"
        assert "timestamp" in event

    def test_event_optional_fields(self):
        """Event works with optional fields"""
        event = _event("test_type", "run_123", "goal_456")

        assert event["schema_version"] == "uar.event.v1"
        assert event["type"] == "test_type"
        assert event["skill"] is None
        assert event["payload"] == {}
        assert event["error"] is None
        assert event["correlation_id"] == ""


class TestExecutor:
    """Test Executor class"""

    def test_iter_events_missing_skills(self):
        """Missing skills returns failed run"""
        goal = GoalSpec(id="test", user_intent="test", objective="test")
        strategy = StrategySpec(
            goal_id="goal_123",
            ordered_skills=["nonexistent_skill"],
        )

        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        assert len(events) >= 2
        assert events[0]["type"] == "start"
        assert events[-1]["type"] == "complete"
        assert events[-1]["payload"]["status"] == "failed"
        assert "not found" in events[-1]["payload"]["errors"][0]

    def test_iter_events_empty_skills(self):
        """Empty skills list raises ValidationError"""
        goal = GoalSpec(id="test", user_intent="test", objective="test")
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])

        executor = Executor()
        with pytest.raises(ValidationError) as exc_info:
            list(executor.iter_events(strategy, goal, timeout_seconds=1.0))
        assert "At least one skill must be specified" in str(exc_info.value)

    def test_iter_events_correlation_id(self):
        """Correlation ID is propagated to events"""
        goal = GoalSpec(id="test", user_intent="test", objective="test")
        strategy = StrategySpec(
            goal_id="goal_123",
            ordered_skills=["nonexistent_skill"],
        )

        executor = Executor()
        events = list(
            executor.iter_events(
                strategy, goal, timeout_seconds=1.0, correlation_id="test_corr"
            )
        )

        for event in events:
            assert event["correlation_id"] == "test_corr"

    @patch("uar.core.executor.registry")
    def test_iter_events_with_registered_skill(self, mock_registry):
        """Registered skill executes successfully"""
        # Mock the registry to return a skill
        mock_skill = Mock(return_value={"status": "completed"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill

        goal = GoalSpec(id="test", user_intent="test", objective="test")
        strategy = StrategySpec(
            goal_id="goal_123",
            ordered_skills=["test_skill"],
        )

        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        # Should have at least start and complete events
        assert len(events) >= 2
        assert events[0]["type"] == "start"
        assert events[-1]["type"] == "complete"
