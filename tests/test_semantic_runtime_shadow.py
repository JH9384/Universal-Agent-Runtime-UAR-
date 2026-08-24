from unittest.mock import Mock, patch

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.exceptions import SkillExecutionError
from uar.core.executor import Executor
from uar.core.semantic_shadow import (
    MAX_OBSERVER_P95_MICROSECONDS_PER_EVENT,
    measure_shadow_observer_overhead,
    pair_runtime_with_shadow,
)
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


@patch("uar.core.executor.registry")
def test_nonretryable_runtime_rejection_emits_one_decision(mock_registry):
    mock_registry.is_registered.return_value = True
    mock_registry.get.return_value = Mock(side_effect=RuntimeError("blocked"))
    goal = GoalSpec(
        id="shadow-reject",
        user_intent="reject invalid work",
        objective="stop once",
        metadata={"enable_cache": False, "enable_parallel": False},
    )
    strategy = StrategySpec(goal_id=goal.id, ordered_skills=["blocked"])

    pair = pair_runtime_with_shadow(
        lambda: Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=1.0,
            _run_id="shadow-reject-fixed-run",
        )
    )

    assert sum(
        event["type"] == "skill_failed" for event in pair.baseline_events
    ) == 1
    assert len(pair.semantic_trace.stages) == 1
    assert len(pair.semantic_trace.stages[0].decisions) == 1
    assert pair.projected_events_equal is True


@patch("uar.core.executor.registry")
def test_parallel_runtime_stages_join_the_full_causal_frontier(mock_registry):
    skills = {
        "left": lambda _: {"branch": "left"},
        "right": lambda _: {"branch": "right"},
        "join": lambda _: {"joined": True},
    }
    mock_registry.is_registered.return_value = True
    mock_registry.get.side_effect = skills.__getitem__

    goal = GoalSpec(
        id="shadow-dag",
        user_intent="exercise a parallel diamond",
        objective="join independent branches",
        metadata={"enable_cache": False, "enable_parallel": True},
    )
    strategy = StrategySpec(
        goal_id=goal.id,
        ordered_skills=["left", "right", "join"],
        waves=[["left", "right"], ["join"]],
    )

    pair = pair_runtime_with_shadow(
        lambda: Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=1.0,
            _run_id="shadow-dag-fixed-run",
        )
    )

    stages = {stage.stage_id: stage for stage in pair.semantic_trace.stages}
    assert stages["runtime:0000:left"].dependencies == ()
    assert stages["runtime:0001:right"].dependencies == ()
    assert set(stages["runtime:0002:join"].dependencies) == {
        "runtime:0000:left",
        "runtime:0001:right",
    }
    assert pair.projected_events_equal is True
    assert validate_semantic_trace(pair.semantic_trace) == ()


@patch("uar.core.executor.time.sleep", return_value=None)
@patch("uar.core.executor.get_max_retries", return_value=1)
@patch("uar.core.executor.registry")
def test_runtime_retry_is_evidence_not_a_second_stage(
    mock_registry, _mock_retries, _mock_sleep
):
    skill = Mock(
        side_effect=[
            SkillExecutionError("retry", original_error=RuntimeError("transient")),
            {"answer": 42},
        ]
    )
    mock_registry.is_registered.return_value = True
    mock_registry.get.return_value = skill
    goal = GoalSpec(
        id="shadow-retry",
        user_intent="recover from a transient failure",
        objective="complete after retry",
        metadata={"enable_cache": False, "enable_parallel": False},
    )
    strategy = StrategySpec(goal_id=goal.id, ordered_skills=["retry"])

    pair = pair_runtime_with_shadow(
        lambda: Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=1.0,
            _run_id="shadow-retry-fixed-run",
        )
    )

    assert len(pair.semantic_trace.stages) == 1
    decision = pair.semantic_trace.stages[0].decisions[0]
    assert len(decision.evidence_refs) == 2
    assert any(ref.startswith("runtime-retry:") for ref in decision.evidence_refs)
    assert pair.projected_events_equal is True


def test_shadow_observer_overhead_stays_inside_predeclared_envelope():
    baseline = (
        {"type": "start", "payload": {"goal": "x"}},
        {"type": "skill_start", "skill": "one", "payload": {}},
        {
            "type": "skill_complete",
            "skill": "one",
            "payload": {"result": {"answer": 42}},
        },
        {
            "type": "complete",
            "payload": {
                "status": "completed",
                "outputs": [{"one": {"answer": 42}}],
                "final_context": {"one": {"answer": 42}},
            },
        },
    )

    report = measure_shadow_observer_overhead(baseline, iterations=250)

    assert report.within_envelope is True
    assert (
        report.p95_microseconds_per_event
        <= MAX_OBSERVER_P95_MICROSECONDS_PER_EVENT
    )
    assert report.shadow_events > report.baseline_events
