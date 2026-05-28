"""Integration tests for recipe nesting and event markers.

Tests the executor's ability to:
1. Expand nested recipes with proper markers
2. Emit recipe_start/recipe_end events at correct positions
3. Handle circular dependency detection
4. Respect max nesting depth limits
5. Support recipe parameters and conditions
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from uar.core.executor import _expand_execution_order_with_markers
from uar.core.recipes import DEFAULT_RECIPES
from uar.core.exceptions import ValidationError


class TestRecipeNesting:
    """Test recipe nesting expansion and marker generation."""

    def test_flat_skill_list(self):
        """Single-level skill list produces no markers."""
        execution_order = [
            {"type": "skill", "content": "sum_sections", "id": "s1"},
            {"type": "skill", "content": "doc_ingest", "id": "s2"},
        ]
        skills, markers = _expand_execution_order_with_markers(execution_order)

        assert skills == ["sum_sections", "doc_ingest"]
        assert markers == []

    def test_single_recipe_expansion(self):
        """Single recipe expands with start/end markers."""
        # Assuming "ingest_and_summarize" recipe exists
        execution_order = [
            {"type": "recipe", "content": "ingest_and_summarize", "id": "r1"},
        ]

        # Skip if recipe doesn't exist in defaults
        if "ingest_and_summarize" not in DEFAULT_RECIPES:
            pytest.skip("Recipe 'ingest_and_summarize' not in defaults")

        skills, markers = _expand_execution_order_with_markers(execution_order)

        # Should have markers for recipe start and end
        start_markers = [m for m in markers if m["kind"] == "start"]
        end_markers = [m for m in markers if m["kind"] == "end"]

        assert len(start_markers) == 1
        assert len(end_markers) == 1
        assert start_markers[0]["recipe_id"] == "ingest_and_summarize"
        assert end_markers[0]["recipe_id"] == "ingest_and_summarize"

    def test_nested_recipe_detection(self):
        """Nested recipes are properly expanded."""
        # Create a nested recipe structure for testing
        test_recipes = {
            "outer_recipe": {
                "skills": ["doc_ingest", "inner_recipe", "sum_sections"]
            },
            "inner_recipe": {
                "skills": ["dependency_map"]
            },
        }

        execution_order = [
            {"type": "recipe", "content": "outer_recipe", "id": "r1"},
        ]

        skills, markers = _expand_execution_order_with_markers(
            execution_order, _recipe_map=test_recipes
        )

        # Should have skills from both recipes
        assert "doc_ingest" in skills
        assert "dependency_map" in skills  # from inner
        assert "sum_sections" in skills

        # Should have markers for both recipes
        recipe_starts = [m for m in markers if m["kind"] == "start"]
        assert len(recipe_starts) == 2  # outer and inner

    def test_circular_dependency_raises(self):
        """Circular recipe references raise ValidationError."""
        test_recipes = {
            "recipe_a": {"skills": ["recipe_b"]},
            "recipe_b": {"skills": ["recipe_a"]},
        }

        execution_order = [
            {"type": "recipe", "content": "recipe_a", "id": "r1"},
        ]

        with pytest.raises(ValidationError) as exc_info:
            _expand_execution_order_with_markers(
                execution_order, _recipe_map=test_recipes
            )

        assert "circular" in str(exc_info.value).lower()

    def test_max_nesting_depth(self):
        """Excessive nesting raises ValidationError."""
        # Create deeply nested recipes
        test_recipes = {}
        for i in range(12):  # More than MAX_RECIPE_DEPTH (10)
            next_name = f"recipe_{i+1}" if i < 11 else "final_skill"
            test_recipes[f"recipe_{i}"] = {"skills": [next_name]}

        # Add final skill
        test_recipes["final_skill"] = {"skills": ["sum_sections"]}

        execution_order = [
            {"type": "recipe", "content": "recipe_0", "id": "r1"},
        ]

        with pytest.raises(ValidationError) as exc_info:
            _expand_execution_order_with_markers(
                execution_order, _recipe_map=test_recipes
            )

        assert "depth" in str(exc_info.value).lower()

    def test_marker_indices_correct(self):
        """Marker indices correctly identify skill positions."""
        test_recipes = {
            "test_recipe": {"skills": ["skill_a", "skill_b"]},
        }

        execution_order = [
            {"type": "skill", "content": "before", "id": "s1"},
            {"type": "recipe", "content": "test_recipe", "id": "r1"},
            {"type": "skill", "content": "after", "id": "s2"},
        ]

        skills, markers = _expand_execution_order_with_markers(
            execution_order, _recipe_map=test_recipes
        )

        # Skills: before, skill_a, skill_b, after
        assert skills == ["before", "skill_a", "skill_b", "after"]

        # Start marker at index 1 (where recipe skills begin)
        start_marker = [m for m in markers if m["kind"] == "start"][0]
        assert start_marker["index"] == 1

        # End marker at index 3 (exclusive end)
        end_marker = [m for m in markers if m["kind"] == "end"][0]
        assert end_marker["index"] == 3

    def test_parallel_skill_groups(self):
        """Parallel skill groups (lists) are handled correctly."""
        test_recipes = {
            "parallel_recipe": {
                "skills": [["skill_a", "skill_b"], "skill_c"]
            },
        }

        execution_order = [
            {"type": "recipe", "content": "parallel_recipe", "id": "r1"},
        ]

        skills, markers = _expand_execution_order_with_markers(
            execution_order, _recipe_map=test_recipes
        )

        # Should expand parallel groups
        assert "skill_a" in skills
        assert "skill_b" in skills
        assert "skill_c" in skills


class TestRecipeConditions:
    """Test recipe conditional execution."""

    def test_condition_evaluation_exists(self):
        """Test 'exists' condition operator."""
        # This would require executor integration test
        # Placeholder for condition testing
        pass

    def test_condition_evaluation_equals(self):
        """Test 'equals' condition operator."""
        pass


class TestRecipeEventEmission:
    """Test that recipe events are properly emitted during execution."""

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_recipe_start_event_structure(
        self, mock_registry, mock_guardrails
    ):
        """Recipe start events have required fields."""
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = Mock(return_value="ok")
        mock_guardrails.return_value = []

        from uar.core.executor import Executor
        from uar.core.contracts import GoalSpec, StrategySpec

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {"type": "recipe", "content": "review", "id": "r1"},
                ]
            },
        )
        strategy = StrategySpec(goal_id="g1", ordered_skills=[])
        events = list(
            Executor().iter_events(strategy, goal, timeout_seconds=1.0)
        )
        starts = [e for e in events if e["type"] == "recipe_start"]
        assert len(starts) == 1
        assert starts[0]["payload"]["recipe_id"] == "review"
        assert starts[0]["payload"]["instance_id"] == "r1"

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_recipe_end_event_includes_duration(
        self, mock_registry, mock_guardrails
    ):
        """Recipe end events include duration."""
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = Mock(return_value="ok")
        mock_guardrails.return_value = []

        from uar.core.executor import Executor
        from uar.core.contracts import GoalSpec, StrategySpec

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {"type": "recipe", "content": "review", "id": "r1"},
                ]
            },
        )
        strategy = StrategySpec(goal_id="g1", ordered_skills=[])
        events = list(
            Executor().iter_events(strategy, goal, timeout_seconds=1.0)
        )
        ends = [e for e in events if e["type"] == "recipe_end"]
        assert len(ends) >= 1
        assert ends[-1]["payload"]["recipe_id"] == "review"
        assert "status" in ends[-1]["payload"]

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_nested_recipe_events(self, mock_registry, mock_guardrails):
        """Nested recipes emit correct event sequences."""
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = Mock(return_value="ok")
        mock_guardrails.return_value = []

        from uar.core.executor import Executor
        from uar.core.contracts import GoalSpec, StrategySpec

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "use_hierarchical": True,
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "parent",
                        "id": "p1",
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "parent",
                        "skills": ["noop"],
                        "items": [
                            {
                                "type": "recipe",
                                "content": "child",
                                "id": "c1",
                            },
                        ],
                    },
                    {
                        "id": "child",
                        "skills": ["noop"],
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="g1", ordered_skills=[])
        events = list(
            Executor().iter_events(strategy, goal, timeout_seconds=1.0)
        )
        types = [e["type"] for e in events]
        assert types.count("recipe_start") >= 2
        assert types.count("recipe_end") >= 2


class TestHierarchicalParallelGroups:
    """Parallel skill groups in recipes under hierarchical execution."""

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_parallel_groups_in_skills_are_executed(
        self, mock_registry, mock_guardrails
    ):
        """A recipe with skills=['a', ['b', 'c']] runs all three skills."""
        call_log = []

        def mock_skill(ctx):
            call_log.append("called")
            return {"status": "ok"}

        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill
        mock_guardrails.return_value = []

        from uar.core.executor import Executor
        from uar.core.contracts import GoalSpec, StrategySpec

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "use_hierarchical": True,
                "execution_order": [
                    {"type": "recipe", "content": "parallel", "id": "p1"},
                ],
                "recipe_definitions": [
                    {
                        "id": "parallel",
                        "skills": ["skill_a", ["skill_b", "skill_c"]],
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="g1", ordered_skills=[])
        events = list(
            Executor().iter_events(strategy, goal, timeout_seconds=1.0)
        )
        # All three skills should have been invoked
        assert len(call_log) == 3
        skill_events = [
            e for e in events if e["type"].startswith("skill_")
        ]
        assert len(skill_events) == 6  # 3 starts + 3 completes
