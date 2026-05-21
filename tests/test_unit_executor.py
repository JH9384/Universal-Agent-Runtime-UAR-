"""Unit tests for executor module"""

import pytest
import time
from unittest.mock import Mock, patch

from uar.core.executor import (
    get_max_retries,
    _run_with_timeout,
    _event,
    _expand_execution_order_with_markers,
    _get_parallel_groups,
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


class TestExpandExecutionOrder:
    """Test _expand_execution_order_with_markers function"""

    def test_expand_skills_only(self):
        """Skills only - no recipes"""
        execution_order = [
            {"type": "skill", "content": "doc_ingest", "id": "s1"},
            {"type": "skill", "content": "sum_review", "id": "s2"},
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order
        )
        assert skills == ["doc_ingest", "sum_review"]
        assert markers == []

    def test_expand_recipe_flat(self):
        """Recipe expands to its skills with markers"""
        execution_order = [
            {"type": "recipe", "content": "review", "id": "r1"},
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order
        )
        assert skills == ["doc_ingest", "ollama_generate"]
        assert len(markers) == 2
        assert markers[0] == {
            "index": 0,
            "kind": "start",
            "recipe_id": "review",
            "instance_id": "r1",
            "max_retries": 0,
            "parameters": {},
            "condition": None,
        }
        assert markers[1] == {
            "index": 2,
            "kind": "end",
            "recipe_id": "review",
            "instance_id": "r1",
        }

    def test_expand_mixed_skills_and_recipes(self):
        """Mix of skills and recipes in order"""
        execution_order = [
            {"type": "skill", "content": "doc_ingest", "id": "s1"},
            {"type": "recipe", "content": "gr_query", "id": "r1"},
            {"type": "skill", "content": "sum_review", "id": "s2"},
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order
        )
        assert skills == [
            "doc_ingest", "graphrag_query", "sum_review"
        ]
        assert len(markers) == 2
        assert markers[0]["index"] == 1  # recipe starts after first skill
        assert markers[0]["kind"] == "start"
        assert markers[1]["index"] == 2  # recipe ends after graphrag_query
        assert markers[1]["kind"] == "end"

    def test_expand_unknown_recipe_raises(self):
        """Unknown recipe raises ValidationError"""
        execution_order = [
            {"type": "recipe", "content": "nonexistent", "id": "r1"},
        ]
        with pytest.raises(ValidationError) as exc_info:
            _expand_execution_order_with_markers(execution_order)
        assert "nonexistent" in str(exc_info.value)

    def test_expand_nested_recipe(self):
        """Nested recipe (recipe containing another recipe)"""
        # Patch DEFAULT_RECIPES to create a recipe that references 'review'
        from uar.core.executor import DEFAULT_RECIPES

        original = DEFAULT_RECIPES.copy()
        try:
            DEFAULT_RECIPES["meta"] = {
                "id": "meta",
                "label": "Meta",
                "skills": ["review", "sum_review"],
            }
            execution_order = [
                {"type": "recipe", "content": "meta", "id": "m1"},
            ]
            skills, markers = _expand_execution_order_with_markers(
                execution_order
            )
            # meta -> review (doc_ingest, ollama_generate) + sum_review
            assert skills == [
                "doc_ingest", "ollama_generate", "sum_review"
            ]
            # Expect 4 markers: meta start, review start, review end, meta end
            assert len(markers) == 4
            assert markers[0]["kind"] == "start"
            assert markers[0]["recipe_id"] == "meta"
            assert markers[0]["index"] == 0
            assert markers[1]["kind"] == "start"
            assert markers[1]["recipe_id"] == "review"
            assert markers[1]["index"] == 0
            assert markers[2]["kind"] == "end"
            assert markers[2]["recipe_id"] == "review"
            assert markers[2]["index"] == 2
            assert markers[3]["kind"] == "end"
            assert markers[3]["recipe_id"] == "meta"
            assert markers[3]["index"] == 3
        finally:
            DEFAULT_RECIPES.clear()
            DEFAULT_RECIPES.update(original)

    def test_expand_circular_recipe_raises(self):
        """Circular recipe dependency raises ValidationError"""
        from uar.core.executor import DEFAULT_RECIPES

        original = DEFAULT_RECIPES.copy()
        try:
            DEFAULT_RECIPES["a"] = {
                "id": "a", "label": "A", "skills": ["b"],
            }
            DEFAULT_RECIPES["b"] = {
                "id": "b", "label": "B", "skills": ["a"],
            }
            execution_order = [
                {"type": "recipe", "content": "a", "id": "a1"},
            ]
            with pytest.raises(ValidationError) as exc_info:
                _expand_execution_order_with_markers(execution_order)
            assert "Circular" in str(exc_info.value)
        finally:
            DEFAULT_RECIPES.clear()
            DEFAULT_RECIPES.update(original)

    def test_expand_max_depth_raises(self):
        """Excessive nesting depth raises ValidationError"""
        from uar.core.executor import DEFAULT_RECIPES, MAX_RECIPE_DEPTH

        original = DEFAULT_RECIPES.copy()
        try:
            # Create a chain of recipes: a1 -> a2 -> a3 -> ... -> aN
            for i in range(1, MAX_RECIPE_DEPTH + 2):
                nxt = f"a{i + 1}" if i <= MAX_RECIPE_DEPTH + 1 else "skill"
                DEFAULT_RECIPES[f"a{i}"] = {
                    "id": f"a{i}",
                    "label": f"A{i}",
                    "skills": (
                        [nxt] if i <= MAX_RECIPE_DEPTH + 1
                        else ["doc_ingest"]
                    ),
                }
            execution_order = [
                {"type": "recipe", "content": "a1", "id": "a1"},
            ]
            with pytest.raises(ValidationError) as exc_info:
                _expand_execution_order_with_markers(execution_order)
            assert "depth" in str(exc_info.value).lower()
        finally:
            DEFAULT_RECIPES.clear()
            DEFAULT_RECIPES.update(original)

    def test_expand_with_custom_recipe_map(self):
        """Expansion with custom recipe map from metadata"""
        custom_map = {
            "custom": {
                "id": "custom",
                "skills": ["doc_ingest"],
            }
        }
        execution_order = [
            {"type": "recipe", "content": "custom", "id": "c1"},
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order,
            _recipe_map=custom_map,
        )
        assert skills == ["doc_ingest"]
        assert len(markers) == 2
        assert markers[0]["recipe_id"] == "custom"

    def test_expand_recipe_with_parallel_groups(self):
        """Recipe with nested lists expands into flat adjacent skills"""
        custom_map = {
            "parallel_test": {
                "id": "parallel_test",
                "skills": [
                    "doc_ingest",
                    ["ollama_generate", "graphrag_query"],
                ],
            }
        }
        execution_order = [
            {
                "type": "recipe",
                "content": "parallel_test",
                "id": "p1",
            },
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order,
            _recipe_map=custom_map,
        )
        assert skills == [
            "doc_ingest",
            "ollama_generate",
            "graphrag_query",
        ]
        assert len(markers) == 2
        assert markers[0]["kind"] == "start"
        assert markers[1]["kind"] == "end"
        # Non-context-modifying adjacent skills will be grouped
        groups = _get_parallel_groups(skills)
        assert groups == [
            ["doc_ingest"],
            ["ollama_generate", "graphrag_query"],
        ]

    def test_expand_recipe_with_parameters(self):
        """Recipe parameters are passed through start marker"""
        custom_map = {
            "param_test": {
                "id": "param_test",
                "skills": ["doc_ingest"],
                "parameters": {"model": "llama3", "temperature": 0.7},
            }
        }
        execution_order = [
            {
                "type": "recipe",
                "content": "param_test",
                "id": "p1",
            },
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order,
            _recipe_map=custom_map,
        )
        assert markers[0]["parameters"] == {
            "model": "llama3",
            "temperature": 0.7,
        }

    def test_expand_recipe_with_condition(self):
        """Recipe condition is passed through start marker"""
        custom_map = {
            "conditional": {
                "id": "conditional",
                "skills": ["doc_ingest"],
                "condition": {"key": "ready", "exists": True},
            }
        }
        execution_order = [
            {
                "type": "recipe",
                "content": "conditional",
                "id": "c1",
            },
        ]
        skills, markers = _expand_execution_order_with_markers(
            execution_order,
            _recipe_map=custom_map,
        )
        assert markers[0]["condition"] == {
            "key": "ready",
            "exists": True,
        }

    @patch("uar.core.executor.registry")
    def test_iter_events_emits_recipe_boundary_events(self, mock_registry):
        """Executor emits recipe_start and recipe_end events"""
        mock_skill = Mock(return_value={"status": "ok"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {"type": "recipe", "content": "gr_query", "id": "r1"},
                ]
            },
        )
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])

        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        types = [e["type"] for e in events]
        assert "orchestration_plan" in types
        assert "recipe_start" in types
        assert "recipe_end" in types
        assert "skill_start" in types
        assert "skill_complete" in types
        assert "complete" in types

        # Verify recipe_start has correct payload
        recipe_start = next(e for e in events if e["type"] == "recipe_start")
        assert recipe_start["payload"]["recipe_id"] == "gr_query"
        assert recipe_start["payload"]["instance_id"] == "r1"

        # recipe_end should come after skill_complete
        recipe_end_idx = types.index("recipe_end")
        skill_complete_idx = types.index("skill_complete")
        assert recipe_end_idx > skill_complete_idx

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_iter_events_emits_recipe_end_on_failure(
        self, mock_registry, mock_guardrails
    ):
        """recipe_end is emitted even when the skill loop breaks early"""
        mock_registry.is_registered.return_value = True
        mock_guardrails.return_value = ["guardrail violation"]

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
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])

        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        types = [e["type"] for e in events]
        assert "recipe_start" in types
        assert "recipe_end" in types
        assert "skill_failed" in types
        assert "complete" in types

        # Verify recipe_end has aborted status because loop broke early
        recipe_end = [e for e in events if e["type"] == "recipe_end"][-1]
        assert recipe_end["payload"]["status"] == "aborted"

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_iter_events_recipe_level_retry(
        self, mock_registry, mock_guardrails
    ):
        """Recipe with max_retries re-executes on skill failure"""
        mock_registry.is_registered.return_value = True
        # First skill attempt fails, second succeeds
        call_count = [0]

        def guardrails_side_effect(ctx, skill):
            call_count[0] += 1
            return ["fail"] if call_count[0] <= 1 else []

        mock_guardrails.side_effect = guardrails_side_effect

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "review",
                        "id": "r1",
                        "max_retries": 1,
                    },
                ]
            },
        )
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])

        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        types = [e["type"] for e in events]
        assert types.count("recipe_start") == 2  # initial + retry
        assert types.count("recipe_retry") == 1
        assert types.count("recipe_end") == 1
        assert types.count("skill_failed") == 1
        assert "complete" in types

        # Verify recipe_end has complete status (not aborted)
        recipe_end = [e for e in events if e["type"] == "recipe_end"][-1]
        assert recipe_end["payload"].get("status") is None


class TestRecipeCaching:
    """Tests for recipe-level caching in hierarchical execution."""

    @pytest.fixture(autouse=True)
    def _enable_hierarchical(self, monkeypatch):
        monkeypatch.setenv("UAR_HIERARCHICAL_EXECUTION", "1")

    @pytest.fixture(autouse=True)
    def _register_noop(self):
        from uar.core.registry import registry

        def _noop_skill(ctx: PipelineContext):
            ctx.data["noop_ran"] = True
            return "done"

        if not registry.is_registered("noop"):
            registry.register("noop", _noop_skill)
        yield

    def test_recipe_caches_context_delta(self):
        """A recipe with cache=true stores its context mutations."""
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r1",
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "cached_recipe",
                        "skills": ["noop"],
                        "cache": True,
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="test", ordered_skills=[])
        executor = Executor()

        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )
        types = [e["type"] for e in events]
        assert "recipe_end" in types

        # The recipe should have cached the noop mutation
        assert len(executor._recipe_cache) == 1
        cached = list(executor._recipe_cache.values())[0]
        assert cached.get("noop_ran") is True

    def test_recipe_cache_hit_replays_delta(self):
        """Second run of the same recipe with same params is a cache hit."""
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r1",
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "cached_recipe",
                        "skills": ["noop"],
                        "cache": True,
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="test", ordered_skills=[])
        executor = Executor()

        # First run — cache miss
        events1 = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )
        assert all(
            not e.get("payload", {}).get("cached")
            for e in events1
            if e["type"] in ("recipe_start", "recipe_end")
        )

        # Second run — cache hit (same executor, same cache)
        events2 = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )
        starts = [
            e for e in events2 if e["type"] == "recipe_start"
        ]
        ends = [e for e in events2 if e["type"] == "recipe_end"]
        assert starts[0]["payload"].get("cached") is True
        assert ends[0]["payload"].get("cached") is True

        # No skill events on cache hit
        skill_events = [e for e in events2 if e["type"].startswith("skill_")]
        assert len(skill_events) == 0

    def test_different_params_different_cache(self):
        """Recipes with different params should not share cache entries."""
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r1",
                        "parameters": {"mode": "fast"},
                    },
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r2",
                        "parameters": {"mode": "slow"},
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "cached_recipe",
                        "skills": ["noop"],
                        "cache": True,
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="test", ordered_skills=[])
        executor = Executor()

        list(executor.iter_events(strategy, goal, timeout_seconds=1.0))
        assert len(executor._recipe_cache) == 2

    def test_failed_recipe_not_cached(self):
        """Failed recipes should not be cached."""
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r1",
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "cached_recipe",
                        "skills": ["unknown_skill"],
                        "cache": True,
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="test", ordered_skills=[])
        executor = Executor()

        list(executor.iter_events(strategy, goal, timeout_seconds=1.0))
        assert len(executor._recipe_cache) == 0


class TestRecipeTimeout:
    """Tests for recipe-level timeout override hook."""

    def test_recipe_timeout_reads_definition(self):
        """_recipe_timeout returns recipe's timeout field when present."""
        executor = Executor()
        recipe = {"id": "fast", "timeout": 2.5, "skills": []}
        assert executor._recipe_timeout("fast", 30.0, recipe) == 2.5

    def test_recipe_timeout_fallback_to_default(self):
        """_recipe_timeout falls back to default when recipe has no timeout."""
        executor = Executor()
        recipe = {"id": "slow", "skills": []}
        assert executor._recipe_timeout("slow", 30.0, recipe) == 30.0

    def test_recipe_timeout_none_recipe(self):
        """_recipe_timeout falls back to default when recipe is None."""
        executor = Executor()
        assert executor._recipe_timeout("missing", 15.0, None) == 15.0


class TestRecipeCacheEviction:
    """Tests for recipe cache size limiting."""

    @pytest.fixture(autouse=True)
    def _enable_hierarchical(self, monkeypatch):
        monkeypatch.setenv("UAR_HIERARCHICAL_EXECUTION", "1")

    @pytest.fixture(autouse=True)
    def _register_noop(self):
        from uar.core.registry import registry

        def _noop_skill(ctx: PipelineContext):
            ctx.data["noop_ran"] = True
            return "done"

        if not registry.is_registered("noop"):
            registry.register("noop", _noop_skill)
        yield

    @patch("uar.core.executor.registry")
    def test_cache_evicts_oldest_when_over_limit(self, mock_registry):
        """Cache evicts oldest entry when exceeding max size."""
        mock_skill = Mock(return_value={"status": "ok"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill

        executor = Executor()
        # Manually fill cache beyond limit
        for i in range(55):
            executor._recipe_cache[f"key_{i}"] = {"idx": i}
        assert len(executor._recipe_cache) == 55

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "execution_order": [
                    {
                        "type": "recipe",
                        "content": "cached_recipe",
                        "id": "r1",
                    },
                ],
                "recipe_definitions": [
                    {
                        "id": "cached_recipe",
                        "skills": ["noop"],
                        "cache": True,
                    },
                ],
            },
        )
        strategy = StrategySpec(goal_id="test", ordered_skills=[])
        list(executor.iter_events(strategy, goal, timeout_seconds=1.0))
        assert len(executor._recipe_cache) <= 50


class TestUseHierarchicalMetadata:
    """Tests that use_hierarchical in goal metadata triggers
    hierarchical mode."""

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_use_hierarchical_metadata_flag(
        self, mock_registry, mock_guardrails
    ):
        """Hierarchical execution triggered by metadata flag
        without env var."""
        mock_skill = Mock(return_value={"status": "ok"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "use_hierarchical": True,
                "execution_order": [
                    {"type": "recipe", "content": "gr_query", "id": "r1"},
                ],
            },
        )
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])
        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )
        types = [e["type"] for e in events]
        assert "recipe_start" in types
        assert "recipe_end" in types

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_use_hierarchical_false_uses_flat(
        self, mock_registry, mock_guardrails
    ):
        """use_hierarchical=False falls back to flat expansion."""
        mock_skill = Mock(return_value={"status": "ok"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill

        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={
                "use_hierarchical": False,
                "execution_order": [
                    {"type": "recipe", "content": "gr_query", "id": "r1"},
                ],
            },
        )
        strategy = StrategySpec(goal_id="goal_123", ordered_skills=[])
        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )
        types = [e["type"] for e in events]
        # Flat mode should still emit recipe_start/recipe_end via markers
        assert "recipe_start" in types
        assert "recipe_end" in types
        assert "skill_start" in types
        assert "skill_complete" in types


class TestDeepNesting:
    """Tests for deeply nested recipe execution with parameter scoping."""

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_nested_recipe_emits_boundary_events(
        self, mock_registry, mock_guardrails
    ):
        """Nested recipes emit recipe_start/recipe_end in correct order."""
        mock_skill = Mock(return_value={"status": "ok"})
        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = mock_skill
        mock_guardrails.return_value = []

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
        strategy = StrategySpec(goal_id="goal", ordered_skills=[])
        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        types = [e["type"] for e in events]
        # Must have at least parent + child start/end events
        assert types.count("recipe_start") >= 2
        assert types.count("recipe_end") >= 2
        # Child start should come after parent start
        parent_start = types.index("recipe_start")
        child_start = types.index("recipe_start", parent_start + 1)
        assert child_start > parent_start
        # Child end should come before parent end
        parent_end = types.index("recipe_end")
        child_end = types.index("recipe_end", parent_end + 1)
        assert child_end > child_start

    @patch("uar.core.executor._validate_input_guardrails")
    @patch("uar.core.executor.registry")
    def test_nested_recipe_params_stack_preserves_parent(
        self, mock_registry, mock_guardrails
    ):
        """Parent recipe params are not wiped when child recipe ends."""
        def skill_that_reads_params(ctx):
            stack = ctx.data.get("_recipe_params", [])
            # Record how deep the stack is at execution time
            ctx.data["stack_depth"] = len(stack)
            return {"status": "ok"}

        mock_registry.is_registered.return_value = True
        mock_registry.get.return_value = skill_that_reads_params
        mock_guardrails.return_value = []

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
                        "parameters": {"a": 1},
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
                                "parameters": {"b": 2},
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
        strategy = StrategySpec(goal_id="goal", ordered_skills=[])
        executor = Executor()
        events = list(
            executor.iter_events(strategy, goal, timeout_seconds=1.0)
        )

        # The skill inside child recipe writes stack_depth to ctx.data.
        # Verify via final_context after execution completes.
        complete_event = [e for e in events if e["type"] == "complete"][-1]
        final_ctx = complete_event["payload"]["final_context"]
        assert final_ctx.get("stack_depth") == 2
