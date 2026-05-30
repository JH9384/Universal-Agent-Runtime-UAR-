"""Tests for uar.core.orchestrator.

Covers compute_parallel_waves, build_orchestration_plan, and
OrchestrationPlan data-class helpers.
"""

from uar.core.contracts import StrategySpec
from uar.core.orchestrator import (
    OrchestrationNode,
    OrchestrationPlan,
    build_orchestration_plan,
    compute_parallel_waves,
)


class TestComputeParallelWaves:
    """Tests for compute_parallel_waves dependency scheduler."""

    def test_empty_skills_returns_empty(self):
        assert compute_parallel_waves([]) == []

    def test_single_skill_single_wave(self):
        assert compute_parallel_waves(["a"]) == [["a"]]

    def test_independent_skills_same_wave(self):
        assert compute_parallel_waves(["a", "b", "c"]) == [["a", "b", "c"]]

    def test_simple_dependency_chain(self):
        deps = {
            "b": {"reads": ["a"], "writes": ["b"]},
            "c": {"reads": ["b"], "writes": ["c"]},
        }
        waves = compute_parallel_waves(["a", "b", "c"], deps)
        assert waves == [["a"], ["b"], ["c"]]

    def test_diamond_dependency(self):
        """Diamond: a writes x; b and c read x; d reads b and c."""
        deps = {
            "a": {"reads": [], "writes": ["x"]},
            "b": {"reads": ["x"], "writes": ["y"]},
            "c": {"reads": ["x"], "writes": ["z"]},
            "d": {"reads": ["y", "z"], "writes": ["d"]},
        }
        waves = compute_parallel_waves(["a", "b", "c", "d"], deps)
        assert waves[0] == ["a"]
        assert set(waves[1]) == {"b", "c"}
        assert waves[2] == ["d"]

    def test_conflicting_writes_split_waves(self):
        """Skills writing the same key cannot share a wave."""
        deps = {
            "a": {"reads": [], "writes": ["x"]},
            "b": {"reads": [], "writes": ["x"]},
        }
        waves = compute_parallel_waves(["a", "b"], deps)
        assert len(waves) == 2
        assert waves[0] == ["a"]
        assert waves[1] == ["b"]

    def test_dependency_deadlock_breaks_cycle(self):
        """Circular read/write deps force skills into separate waves."""
        deps = {
            "a": {"reads": ["b"], "writes": ["a"]},
            "b": {"reads": ["a"], "writes": ["b"]},
        }
        waves = compute_parallel_waves(["a", "b"], deps)
        # Deadlock forces first skill into its own wave
        assert len(waves) >= 1
        assert waves[0] == ["a"]

    def test_no_dependency_map_all_independent(self):
        waves = compute_parallel_waves(["x", "y", "z"])
        assert waves == [["x", "y", "z"]]

    def test_skill_without_entry_uses_default_writes(self):
        """Skill with no entry in dependency_map writes its own name."""
        deps = {
            "a": {"reads": [], "writes": ["x"]},
        }
        waves = compute_parallel_waves(["a", "b"], deps)
        # b writes "b" by default, a writes "x"; no conflict
        assert waves == [["a", "b"]]


class TestOrchestrationPlan:
    """Tests for OrchestrationPlan dataclass helpers."""

    def test_ordered_skills(self):
        plan = OrchestrationPlan(
            goal_id="g1",
            nodes=[
                OrchestrationNode(id="n1", skill="s1"),
                OrchestrationNode(id="n2", skill="s2"),
            ],
        )
        assert plan.ordered_skills() == ["s1", "s2"]

    def test_to_strategy(self):
        plan = OrchestrationPlan(
            goal_id="g1",
            nodes=[
                OrchestrationNode(id="n1", skill="s1"),
            ],
        )
        strategy = plan.to_strategy()
        assert isinstance(strategy, StrategySpec)
        assert strategy.goal_id == "g1"
        assert strategy.ordered_skills == ["s1"]

    def test_to_graph(self):
        plan = OrchestrationPlan(
            goal_id="g1",
            nodes=[
                OrchestrationNode(id="n1", skill="s1", depends_on=["n0"]),
                OrchestrationNode(id="n2", skill="s2"),
            ],
            mode="dag",
            waves=[["s1"], ["s2"]],
        )
        graph = plan.to_graph()
        assert graph["mode"] == "dag"
        assert graph["waves"] == [["s1"], ["s2"]]
        assert len(graph["nodes"]) == 2
        assert graph["edges"] == [{"from": "n0", "to": "n1"}]


class TestBuildOrchestrationPlan:
    """Tests for build_orchestration_plan."""

    def test_linear_chain_without_deps(self):
        strategy = StrategySpec(
            goal_id="g1", ordered_skills=["a", "b", "c"]
        )
        plan = build_orchestration_plan(strategy)
        assert plan.mode == "sequential"
        assert plan.waves == [["a"], ["b"], ["c"]]
        assert plan.nodes[0].depends_on == []
        assert plan.nodes[1].depends_on == ["skill-1-a"]
        assert plan.nodes[2].depends_on == ["skill-2-b"]

    def test_dag_mode_with_dependency_map(self):
        strategy = StrategySpec(
            goal_id="g1", ordered_skills=["a", "b", "c"]
        )
        deps = {
            "b": {"reads": ["a"], "writes": ["b"]},
            "c": {"reads": ["b"], "writes": ["c"]},
        }
        plan = build_orchestration_plan(strategy, deps)
        assert plan.mode == "dag"
        assert plan.waves == [["a"], ["b"], ["c"]]
        # b depends on a's node id
        assert plan.nodes[1].depends_on == [plan.nodes[0].id]

    def test_empty_strategy(self):
        strategy = StrategySpec(goal_id="g1", ordered_skills=[])
        plan = build_orchestration_plan(strategy)
        assert plan.nodes == []
        assert plan.waves == []

    def test_unregistered_skill_metadata(self):
        strategy = StrategySpec(
            goal_id="g1", ordered_skills=["definitely_not_a_real_skill_12345"]
        )
        plan = build_orchestration_plan(strategy)
        assert plan.nodes[0].metadata == {"registered": False}

    def test_registered_skill_metadata(self):
        from uar.core.registry import registry

        def _noop(ctx):
            return "ok"

        registry.register("test_orchestrator_noop", _noop)
        try:
            strategy = StrategySpec(
                goal_id="g1", ordered_skills=["test_orchestrator_noop"]
            )
            plan = build_orchestration_plan(strategy)
            assert plan.nodes[0].metadata == {"registered": True}
        finally:
            registry._skills.pop("test_orchestrator_noop", None)
            registry._trie.remove("test_orchestrator_noop")

    def test_registered_skill_metadata_with_deps(self):
        """DAG path must also mark registered skills correctly."""
        from uar.core.registry import registry

        def _noop(ctx):
            return "ok"

        registry.register("test_orchestrator_dag", _noop)
        try:
            strategy = StrategySpec(
                goal_id="g1", ordered_skills=["test_orchestrator_dag", "a"]
            )
            deps = {
                "test_orchestrator_dag": {"reads": [], "writes": ["x"]},
                "a": {"reads": ["y"], "writes": ["a"]},  # y never written
            }
            plan = build_orchestration_plan(strategy, deps)
            assert plan.nodes[0].metadata == {"registered": True}
            assert plan.nodes[1].depends_on == []  # y not in written_by
        finally:
            registry._skills.pop("test_orchestrator_dag", None)
            registry._trie.remove("test_orchestrator_dag")

    def test_duplicate_dependency_skipped(self):
        """Two reads from same writer → second skips duplicate dep."""
        from uar.core.registry import registry

        def _noop(ctx):
            return "ok"

        registry.register("test_orchestrator_w", _noop)
        registry.register("test_orchestrator_r", _noop)
        try:
            strategy = StrategySpec(
                goal_id="g1",
                ordered_skills=["test_orchestrator_w", "test_orchestrator_r"],
            )
            deps = {
                "test_orchestrator_w": {"reads": [], "writes": ["x", "y"]},
                "test_orchestrator_r": {"reads": ["x", "y"], "writes": ["z"]},
            }
            plan = build_orchestration_plan(strategy, deps)
            reader_node = plan.nodes[1]
            assert len(reader_node.depends_on) == 1
        finally:
            for name in ("test_orchestrator_w", "test_orchestrator_r"):
                registry._skills.pop(name, None)
                registry._trie.remove(name)
