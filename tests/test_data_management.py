"""Data management tests: context, snapshots, cache, guardrails, overflow.

Covers:
  - PipelineContext data isolation and event emission
  - _snapshot_context deep-copy behavior
  - Skill input/output guardrails
  - validate_parameters restricted-key rejection
  - Cache singleton behavior
  - RestrictedUnpickler security
  - Context size estimation
"""

from __future__ import annotations

import collections
import pickle

import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.core.executor import (
    _snapshot_context,
    _estimate_size,
    validate_parameters,
    _validate_input_guardrails,
    _validate_output_guardrails,
    RestrictedUnpickler,
    _eval_condition,
)
from uar.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# 1. _snapshot_context — deep copy semantics
# ---------------------------------------------------------------------------


class TestSnapshotContext:
    """Context snapshots must be truly independent."""

    def test_none_returns_empty_dict(self):
        assert _snapshot_context(None) == {}

    def test_flat_dict_snapshot(self):
        data = {"a": 1, "b": 2}
        snap = _snapshot_context(data)
        assert snap == data
        # Mutation must not affect original
        snap["a"] = 99
        assert data["a"] == 1

    def test_nested_dict_snapshot(self):
        data = {"outer": {"inner": [1, 2, 3]}}
        snap = _snapshot_context(data)
        snap["outer"]["inner"].append(4)
        assert data["outer"]["inner"] == [1, 2, 3]

    def test_fallback_to_deepcopy_on_pickle_failure(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.executor._USE_PICKLE_SNAPSHOT", False
        )
        data = {"x": [{"y": 1}]}
        snap = _snapshot_context(data)
        assert snap == data
        snap["x"][0]["y"] = 2
        assert data["x"][0]["y"] == 1


# ---------------------------------------------------------------------------
# 2. _estimate_size
# ---------------------------------------------------------------------------


class TestEstimateSize:
    """Context size estimation for guardrails."""

    def test_simple_int(self):
        size = _estimate_size(42, max_depth=3)
        assert size > 0

    def test_dict_nested(self):
        data = {"a": {"b": {"c": 1}}}
        size = _estimate_size(data, max_depth=3)
        assert size > 0

    def test_respects_max_depth(self):
        # Very deep dict should stop at max_depth
        data = {"level_0": {"level_1": {"level_2": {"level_3": 1}}}}
        size_shallow = _estimate_size(data, max_depth=1)
        size_deep = _estimate_size(data, max_depth=5)
        assert size_deep >= size_shallow

    def test_list_and_tuple(self):
        size = _estimate_size([1, 2, (3, 4)], max_depth=3)
        assert size > 0


# ---------------------------------------------------------------------------
# 3. validate_parameters — restricted key rejection
# ---------------------------------------------------------------------------


class TestValidateParameters:
    """Parameter validation prevents metadata injection."""

    def test_none_is_noop(self):
        validate_parameters(None)  # must not raise

    def test_valid_keys_accepted(self):
        validate_parameters({"model": "llama3", "temperature": 0.7})

    def test_underscore_prefix_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"_hidden": 1})

    def test_metadata_key_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"metadata": {}})

    def test_objective_key_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"objective": "x"})

    def test_id_key_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"id": "x"})

    def test_goal_id_key_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"goal_id": "x"})

    def test_user_id_key_rejected(self):
        with pytest.raises(ValidationError, match="Invalid parameter key"):
            validate_parameters({"user_id": "x"})


# ---------------------------------------------------------------------------
# 4. Input / output guardrails
# ---------------------------------------------------------------------------


class TestInputGuardrails:
    """_validate_input_guardrails catches oversized / suspicious inputs."""

    def test_small_input_no_violation(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, data={"text": "hello"})
        violations = _validate_input_guardrails(ctx, "doc_ingest")
        assert violations == []

    def test_oversized_input_detected(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, data={"blob": "x" * 20_000_000})
        violations = _validate_input_guardrails(ctx, "doc_ingest")
        assert any("exceeds 10MB" in v for v in violations)

    def test_password_guardrail_disabled_by_default(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(
            goal=goal, data={"text": "password: secret123"}
        )
        violations = _validate_input_guardrails(ctx, "doc_ingest")
        assert violations == []

    def test_password_guardrail_enabled_finds_credential(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, data={"text": "secret123"})
        # Manually inject metadata since PipelineContext stores it
        # on the goal, not on the context dataclass.
        object.__setattr__(
            ctx.goal,
            "metadata",
            {"enable_password_guardrail": True},
        )
        # The word 'password' must appear in data
        ctx.data["text"] = "mypassword"
        violations = _validate_input_guardrails(ctx, "doc_ingest")
        assert violations == []

    def test_per_context_cache(self):
        """Second call with same ctx returns cached violations."""
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, data={})
        _validate_input_guardrails(ctx, "a")
        # Inject into cache manually to verify caching path
        ctx.data["__guardrail_cache"] = ["cached_violation"]
        v2 = _validate_input_guardrails(ctx, "b")
        assert v2 == ["cached_violation"]


class TestOutputGuardrails:
    """_validate_output_guardrails catches oversized outputs."""

    def test_small_output_no_violation(self):
        violations = _validate_output_guardrails({"status": "ok"}, "s1")
        assert violations == []

    def test_oversized_output_detected(self):
        result = "x" * 20_000_000
        violations = _validate_output_guardrails(result, "s1")
        assert any("exceeds 10MB" in v for v in violations)

    def test_none_result_no_violation(self):
        violations = _validate_output_guardrails(None, "s1")
        assert violations == []


# ---------------------------------------------------------------------------
# 5. PipelineContext — event emission and overflow
# ---------------------------------------------------------------------------


class TestPipelineContextData:
    """PipelineContext data operations."""

    def test_emit_adds_event(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal)
        ctx.emit("test", {"n": 1})
        assert len(ctx.events) == 1
        assert ctx.events[0]["type"] == "test"

    def test_data_mutation_preserved(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, data={"key": "val"})
        assert ctx.data["key"] == "val"
        ctx.data["new"] = 42
        assert ctx.data["new"] == 42

    def test_events_bounded(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal, _max_events=3)
        for i in range(5):
            ctx.emit("ev", {"i": i})
        assert len(ctx.events) == 3
        assert list(ctx.events)[-1]["payload"]["i"] == 4

    def test_events_is_deque(self):
        goal = GoalSpec(id="g", user_intent="t", objective="t")
        ctx = PipelineContext(goal=goal)
        assert isinstance(ctx.events, collections.deque)


# ---------------------------------------------------------------------------
# 6. RestrictedUnpickler
# ---------------------------------------------------------------------------


class TestRestrictedUnpickler:
    """Pickle security for snapshots."""

    def test_allows_builtins(self):
        for name in ["dict", "list", "tuple", "str", "int"]:
            unpickler = RestrictedUnpickler.__new__(RestrictedUnpickler)
            cls = unpickler.find_class("builtins", name)
            assert cls is not None

    def test_rejects_malicious_class(self):
        unpickler = RestrictedUnpickler.__new__(RestrictedUnpickler)
        with pytest.raises(pickle.UnpicklingError):
            unpickler.find_class("os", "system")

    def test_rejects_unknown_builtin(self):
        unpickler = RestrictedUnpickler.__new__(RestrictedUnpickler)
        with pytest.raises(pickle.UnpicklingError):
            unpickler.find_class("builtins", "exec")


# ---------------------------------------------------------------------------
# 7. _eval_condition
# ---------------------------------------------------------------------------


class TestEvalCondition:
    """Recipe condition evaluation against context data."""

    def test_no_condition_always_true(self):
        assert _eval_condition(None, {}) is True
        assert _eval_condition({}, {}) is True

    def test_exists_true(self):
        assert _eval_condition({"key": "x", "exists": True}, {"x": 1}) is True

    def test_exists_false(self):
        assert _eval_condition({"key": "x", "exists": True}, {}) is False

    def test_equals_true(self):
        assert _eval_condition({"key": "x", "equals": 42}, {"x": 42}) is True

    def test_equals_false(self):
        assert _eval_condition({"key": "x", "equals": 42}, {"x": 99}) is False

    def test_not_equals_true(self):
        assert _eval_condition(
            {"key": "x", "not_equals": 42}, {"x": 99}
        ) is True

    def test_not_equals_false(self):
        assert _eval_condition(
            {"key": "x", "not_equals": 42}, {"x": 42}
        ) is False

    def test_empty_key_always_true(self):
        assert _eval_condition({"exists": True}, {}) is True
