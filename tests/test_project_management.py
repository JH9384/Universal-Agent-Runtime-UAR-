"""Project management tests: goals, runs, recipes, batch execution, pagination.

Covers:
  - GoalSpec construction and metadata handling
  - RunRequest validation (execution_order, skills, timeouts)
  - _build_goal with execution_order and recipe_definitions
  - Recipe CRUD service behavior
  - Recipe validation and migration
  - Batch execution and result pagination
  - RunRecord serialization round-trip
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from uar.api.models import RunRequest, RunResponse
from uar.api.goal_builder import _build_goal
from uar.core.contracts import GoalSpec, RunRecord, StrategySpec
from uar.core.exceptions import ValidationError
from uar.core.recipes import (
    validate_recipe,
    migrate_recipe,
    get_recipe_skills,
)
from uar.core.executor import Executor


# ---------------------------------------------------------------------------
# 1. GoalSpec / RunRequest construction
# ---------------------------------------------------------------------------


class TestRunRequestValidation:
    """RunRequest Pydantic model validation."""

    def test_minimal_request(self):
        req = RunRequest(goal="test goal")
        assert req.goal == "test goal"
        assert req.skills is None
        assert req.execution_order is None

    def test_request_with_skills(self):
        req = RunRequest(goal="test", skills=["doc_ingest", "sum_review"])
        assert req.skills == ["doc_ingest", "sum_review"]

    def test_request_with_execution_order(self):
        req = RunRequest(
            goal="test",
            execution_order=[
                {"type": "skill", "content": "doc_ingest", "id": "s1"},
                {"type": "recipe", "content": "review", "id": "r1"},
            ],
        )
        assert len(req.execution_order) == 2
        assert req.execution_order[0]["type"] == "skill"

    def test_execution_order_rejects_invalid_type(self):
        with pytest.raises(ValueError, match="invalid type"):
            RunRequest(
                goal="test",
                execution_order=[
                    {"type": "invalid", "content": "x", "id": "i1"},
                ],
            )

    def test_execution_order_rejects_duplicate_ids(self):
        with pytest.raises(ValueError, match="duplicate ID"):
            RunRequest(
                goal="test",
                execution_order=[
                    {"type": "skill", "content": "doc_ingest", "id": "same"},
                    {"type": "skill", "content": "sum_review", "id": "same"},
                ],
            )

    def test_execution_order_rejects_missing_fields(self):
        with pytest.raises(ValueError, match="missing required field"):
            RunRequest(
                goal="test",
                execution_order=[{"type": "skill"}],
            )

    def test_timeout_validation_rejects_negative(self):
        with pytest.raises(Exception, match="at least"):
            RunRequest(goal="test", timeout_seconds=-1.0)

    def test_timeout_validation_rejects_zero(self):
        with pytest.raises(Exception, match="at least"):
            RunRequest(goal="test", timeout_seconds=0.0)

    def test_timeout_validation_accepts_positive(self):
        req = RunRequest(goal="test", timeout_seconds=5.0)
        assert req.timeout_seconds == 5.0

    def test_idempotency_key_optional(self):
        req = RunRequest(goal="test", idempotency_key="key-123")
        assert req.idempotency_key == "key-123"


class TestGoalBuilder:
    """_build_goal constructs GoalSpec correctly from RunRequest."""

    def test_basic_goal(self):
        req = RunRequest(goal="summarize docs")
        goal = _build_goal(req)
        assert isinstance(goal, GoalSpec)
        assert goal.objective == "summarize docs"
        assert goal.user_intent == "summarize docs"
        assert goal.id.startswith("api-")
        assert goal.required_skills == []

    def test_goal_with_skills(self):
        req = RunRequest(goal="test", skills=["doc_ingest", "sum_review"])
        goal = _build_goal(req)
        assert goal.required_skills == ["doc_ingest", "sum_review"]

    def test_execution_order_stored_in_metadata(self):
        eo = [
            {"type": "skill", "content": "doc_ingest", "id": "s1"},
        ]
        req = RunRequest(goal="test", execution_order=eo)
        goal = _build_goal(req)
        assert goal.metadata["execution_order"] == eo

    def test_recipe_definitions_in_metadata(self):
        eo = [{"type": "recipe", "content": "custom", "id": "r1"}]
        defs = [{"id": "custom", "skills": ["doc_ingest"]}]
        req = RunRequest(
            goal="test",
            execution_order=eo,
            metadata={"recipe_definitions": defs},
        )
        goal = _build_goal(req)
        assert "recipe_definitions" in goal.metadata
        recipes = {
            r["id"]: r for r in goal.metadata["recipe_definitions"]
        }
        assert "custom" in recipes

    def test_unknown_recipe_in_execution_order_raises(self):
        eo = [{"type": "recipe", "content": "ghost", "id": "r1"}]
        req = RunRequest(goal="test", execution_order=eo)
        with pytest.raises(ValidationError) as exc_info:
            _build_goal(req)
        assert "ghost" in str(exc_info.value)

    def test_user_metadata_passes_through(self):
        req = RunRequest(
            goal="test",
            metadata={"custom_key": "custom_value", "ollama_model": "phi"},
        )
        goal = _build_goal(req)
        assert goal.metadata["custom_key"] == "custom_value"
        assert goal.metadata["ollama_model"] == "phi"

    def test_protected_metadata_keys_not_overridden(self):
        req = RunRequest(
            goal="test",
            input_path="docs/readme.md",
            timeout_seconds=10.0,
            metadata={
                "input_path": "/hacked",
                "timeout_seconds": 999.0,
            },
        )
        goal = _build_goal(req)
        assert goal.metadata["input_path"] == "docs/readme.md"
        assert goal.metadata["timeout_seconds"] == 10.0

    def test_use_hierarchical_metadata(self):
        req = RunRequest(
            goal="test",
            use_hierarchical=True,
        )
        goal = _build_goal(req)
        assert goal.metadata["use_hierarchical"] is True

    def test_empty_skills_with_execution_order(self):
        eo = [
            {"type": "skill", "content": "doc_ingest", "id": "s1"},
        ]
        req = RunRequest(goal="test", execution_order=eo)
        goal = _build_goal(req)
        # skills should remain empty; executor expands from execution_order
        assert goal.required_skills == []


# ---------------------------------------------------------------------------
# 2. Recipe validation / migration / lookup
# ---------------------------------------------------------------------------


class TestRecipeValidation:
    """validate_recipe schema checks."""

    def test_valid_recipe(self):
        recipe = {
            "id": "test",
            "label": "Test",
            "skills": ["doc_ingest", "sum_review"],
        }
        errors = validate_recipe(recipe)
        assert errors == []

    def test_missing_id(self):
        errors = validate_recipe({"label": "X", "skills": ["a"]})
        assert any("missing or invalid 'id'" in e for e in errors)

    def test_missing_label(self):
        errors = validate_recipe({"id": "x", "skills": ["a"]})
        assert any("missing or invalid 'label'" in e for e in errors)

    def test_skills_must_be_list(self):
        errors = validate_recipe(
            {"id": "x", "label": "X", "skills": "not_a_list"}
        )
        assert any("'skills' must be a list" in e for e in errors)

    def test_empty_skill_string_rejected(self):
        errors = validate_recipe(
            {"id": "x", "label": "X", "skills": [""]}
        )
        assert any("non-empty string" in e for e in errors)

    def test_parallel_group_accepted(self):
        errors = validate_recipe(
            {
                "id": "x",
                "label": "X",
                "skills": ["a", ["b", "c"]],
            }
        )
        assert errors == []

    def test_invalid_condition_type(self):
        errors = validate_recipe(
            {
                "id": "x",
                "label": "X",
                "skills": ["a"],
                "condition": "not_a_dict",
            }
        )
        assert any("'condition' must be a dict" in e for e in errors)

    def test_invalid_hint_type(self):
        errors = validate_recipe(
            {
                "id": "x",
                "label": "X",
                "skills": ["a"],
                "hint": 123,
            }
        )
        assert any("'hint' must be a string" in e for e in errors)


class TestRecipeMigration:
    """migrate_recipe schema evolution."""

    def test_v1_noop(self):
        recipe = {"id": "x", "label": "X", "skills": ["a"]}
        migrated = migrate_recipe(recipe)
        assert migrated["version"] == "1"

    def test_v1_adds_version_if_missing(self):
        recipe = {"id": "x", "label": "X", "skills": ["a"]}
        migrated = migrate_recipe(dict(recipe))
        assert "version" in migrated


class TestRecipeLookup:
    """get_recipe_skills resolves canonical and user recipes."""

    def test_canonical_recipe_found(self):
        skills = get_recipe_skills("review")
        assert skills == ["doc_ingest", "ollama_generate"]

    def test_unknown_recipe_returns_none(self):
        assert get_recipe_skills("nonexistent_recipe_12345") is None


# ---------------------------------------------------------------------------
# 3. RunRecord construction / serialization
# ---------------------------------------------------------------------------


class TestRunRecord:
    """RunRecord lifecycle and field integrity."""

    def test_default_status_pending(self):
        rr = RunRecord(run_id="r1", goal_id="g1", skills=["a"])
        assert rr.status == "pending"
        assert rr.errors == []
        assert rr.outputs == []

    def test_full_construction(self):
        rr = RunRecord(
            run_id="r1",
            goal_id="g1",
            skills=["a", "b"],
            outputs=[{"a": 1}],
            status="completed",
            errors=[],
            events=[{"type": "start"}],
            final_context={"key": "val"},
            user_id="u1",
            metadata={"source": "test"},
        )
        assert rr.run_id == "r1"
        assert rr.metadata == {"source": "test"}


class TestRunResponseModel:
    """RunResponse Pydantic model."""

    def test_roundtrip(self):
        resp = RunResponse(
            run_id="r1",
            goal_id="g1",
            skills=["a"],
            outputs=[{"result": 42}],
            status="completed",
            errors=[],
            events=[{"type": "complete"}],
            final_context={},
        )
        d = resp.model_dump()
        assert d["run_id"] == "r1"
        assert d["status"] == "completed"


# ---------------------------------------------------------------------------
# 4. Batch execution and pagination
# ---------------------------------------------------------------------------


class TestExecutorBatchAndPaginate:
    """Executor batch and pagination helpers."""

    @patch("uar.core.executor.registry")
    def test_run_batch_sequential(self, mock_registry):
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = Mock(return_value="ok")

        strategies = [
            StrategySpec(goal_id="g1", ordered_skills=["s1"]),
            StrategySpec(goal_id="g2", ordered_skills=["s2"]),
        ]
        goals = [
            GoalSpec(id="g1", user_intent="t", objective="t"),
            GoalSpec(id="g2", user_intent="t", objective="t"),
        ]
        executor = Executor()
        results = executor.run_batch(strategies, goals, timeout_seconds=1.0)
        assert len(results) == 2
        assert all(r.status == "completed" for r in results)

    def test_paginate_results(self):
        executor = Executor()
        data = list(range(25))
        page = executor.paginate_results(data, page=1, page_size=10)
        assert page["items"] == list(range(10))
        assert page["total"] == 25
        assert page["page"] == 1
        assert page["pages"] == 3

    def test_paginate_results_second_page(self):
        executor = Executor()
        data = list(range(25))
        page = executor.paginate_results(data, page=2, page_size=10)
        assert page["items"] == list(range(10, 20))

    def test_paginate_results_empty(self):
        executor = Executor()
        page = executor.paginate_results([], page=1, page_size=10)
        assert page["items"] == []
        assert page["total"] == 0
        assert page["pages"] == 1

    def test_paginate_results_page_size_one(self):
        executor = Executor()
        data = ["a", "b", "c"]
        page = executor.paginate_results(data, page=2, page_size=1)
        assert page["items"] == ["b"]
