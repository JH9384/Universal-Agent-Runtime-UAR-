from unittest.mock import Mock, patch

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor
from uar.core.semantic_shadow import pair_runtime_with_shadow
from uar.core.semantic_trace import (
    SEMANTIC_EVENT_TYPES,
    validate_semantic_trace,
)


@patch("uar.core.executor.registry")
def test_real_executor_stream_has_exact_shadow_projection(mock_registry):
    skill = Mock(return_value={"answer": 42})
    mock_registry.is_registered.return_value = True
    mock_registry.get.return_value = skill

    goal = GoalSpec(
        id="shadow-runtime",
        user_intent="validate shadow observer",
        objective="produce deterministic output",
        metadata={"enable_cache": False, "enable_parallel": False},
    )
    strategy = StrategySpec(
        goal_id=goal.id,
        ordered_skills=["deterministic_skill"],
    )

    pair = pair_runtime_with_shadow(
        lambda: Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=1.0,
            _run_id="shadow-pair-fixed-run",
        )
    )

    assert pair.projected_events_equal is True
    assert pair.baseline_events[0]["type"] == "start"
    assert pair.baseline_events[-1]["type"] == "complete"
    assert any(
        event["type"] in SEMANTIC_EVENT_TYPES for event in pair.shadow_events
    )
    assert pair.semantic_trace.final_result is not None
    assert len(pair.semantic_trace.stages) == 1
    assert validate_semantic_trace(pair.semantic_trace) == ()
    skill.assert_called_once()


def test_shadow_observer_covers_rejection_without_mutating_runtime_events():
    baseline = (
        {"type": "start", "payload": {"goal": "x"}},
        {"type": "skill_start", "skill": "blocked", "payload": {}},
        {
            "type": "skill_failed",
            "skill": "blocked",
            "payload": {"attempts": 1},
            "error": "denied",
        },
        {
            "type": "complete",
            "payload": {"status": "failed", "outputs": [], "final_context": {}},
        },
    )

    pair = pair_runtime_with_shadow(lambda: baseline)

    assert pair.projected_events_equal is True
    stage = pair.semantic_trace.stages[0]
    assert stage.decisions[0].reason_code == "runtime_skill_failed"
    assert pair.baseline_events == baseline
