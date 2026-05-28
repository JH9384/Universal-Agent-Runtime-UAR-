"""Tests for SimplePlanner.

Covers plan generation and caching.
"""

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner


class TestSimplePlanner:
    """Planner skill ordering."""

    def test_default_skills(self):
        planner = SimplePlanner()
        goal = GoalSpec(id="g1", user_intent="test", objective="test")
        strategy = planner.plan(goal)
        assert strategy.goal_id == "g1"
        assert strategy.ordered_skills == ["section_sum"]

    def test_cached_plan(self):
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g1", user_intent="test", objective="test",
            required_skills=["skill_a", "skill_b"],
        )
        strategy1 = planner.plan(goal)
        strategy2 = planner.plan(goal)
        assert strategy1.ordered_skills == ["skill_a", "skill_b"]
        assert strategy2.ordered_skills == ["skill_a", "skill_b"]

    def test_non_string_skills(self):
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g1", user_intent="test", objective="test",
            required_skills=["skill_a", 123],
        )
        strategy = planner.plan(goal)
        assert strategy.goal_id == "g1"
        assert strategy.ordered_skills == ["skill_a", 123]
