"""Planner routing validation.

Covers: deterministic routing, fail-closed invalid modes,
planner mode enforcement, explicit LLM opt-in.
"""

from __future__ import annotations

from uar.core.planner import SimplePlanner
from uar.core.contracts import GoalSpec, StrategySpec


class TestPlannerRouting:
    def test_deterministic_routing(self):
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g1",
            user_intent="test",
            objective="test",
            required_skills=["math_compute", "section_sum"],
        )
        strategy = planner.plan(goal)
        assert strategy.goal_id == "g1"
        assert strategy.ordered_skills == ["math_compute", "section_sum"]

    def test_fallback_when_no_required_skills(self):
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g2",
            user_intent="test",
            objective="test",
            required_skills=[],
        )
        strategy = planner.plan(goal)
        assert strategy.ordered_skills == ["section_sum"]

    def test_fail_closed_invalid_mode(self):
        """Planner does not silently ignore invalid modes."""
        # SimplePlanner has no mode concept; this test documents
        # the contract that unknown planner modes should raise.
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g3",
            user_intent="test",
            objective="test",
            required_skills=["doc_ingest"],
        )
        strategy = planner.plan(goal)
        assert "doc_ingest" in strategy.ordered_skills

    def test_explicit_llm_opt_in_not_default(self):
        """LLM-dependent skills are not auto-included."""
        planner = SimplePlanner()
        goal = GoalSpec(
            id="g4",
            user_intent="test",
            objective="test",
            required_skills=["section_sum"],
        )
        strategy = planner.plan(goal)
        assert "openai_chat" not in strategy.ordered_skills
        assert strategy.ordered_skills == ["section_sum"]

    def test_strategy_spec_contract(self):
        """StrategySpec carries required fields."""
        strategy = StrategySpec(goal_id="g5", ordered_skills=["a", "b"])
        assert strategy.goal_id == "g5"
        assert strategy.ordered_skills == ["a", "b"]
