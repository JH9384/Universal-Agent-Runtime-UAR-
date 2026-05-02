import time

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor
from uar.core.registry import register_skill


@register_skill("slow_skill")
def slow_skill(ctx):
    time.sleep(10)
    return {"done": True}


def test_timeout_triggers_failure():
    goal = GoalSpec(id="t", user_intent="timeout", objective="timeout")
    strategy = StrategySpec(goal_id=goal.id, ordered_skills=["slow_skill"])

    result = Executor().run(strategy, goal, timeout_seconds=1)

    assert result.status == "failed"
    assert result.errors
