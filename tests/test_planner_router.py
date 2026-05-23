from uar.core.contracts import GoalSpec
from uar.core.planner import (
    PlannerRouter,
    RuntimeConfig,
    SimplePlanner,
    RecipePlanner,
)


def build_goal(required_skills=None):
    return GoalSpec(
        id="goal-1",
        user_intent="test",
        objective="test objective",
        constraints=[],
        success_criteria=[],
        required_skills=required_skills or [],
        metadata={},
    )


def test_simple_planner_default_route():
    router = PlannerRouter()
    planner = router.route()

    assert isinstance(planner, SimplePlanner)



def test_recipe_planner_route():
    router = PlannerRouter(RuntimeConfig(planner_mode="recipe"))
    planner = router.route()

    assert isinstance(planner, RecipePlanner)



def test_simple_planner_is_deterministic():
    goal = build_goal(required_skills=["alpha", "beta"])

    router = PlannerRouter(RuntimeConfig(planner_mode="simple"))

    strategy_a = router.plan(goal)
    strategy_b = router.plan(goal)

    assert strategy_a.ordered_skills == ["alpha", "beta"]
    assert strategy_a == strategy_b



def test_simple_planner_fallback_skill():
    goal = build_goal(required_skills=[])

    router = PlannerRouter()
    strategy = router.plan(goal)

    assert strategy.ordered_skills == ["section_sum"]



def test_llm_planner_requires_explicit_opt_in():
    try:
        PlannerRouter(RuntimeConfig(planner_mode="llm")).route()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "allow_llm" in str(exc)



def test_invalid_planner_mode_fails_closed():
    config = RuntimeConfig()
    object.__setattr__(config, "planner_mode", "invalid")

    try:
        PlannerRouter(config).route()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unsupported planner mode" in str(exc)
