from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
import uar.skills.section_sum  # register skill


def test_pipeline():
    goal = GoalSpec(id="1", user_intent="test", objective="test")
    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy, goal)

    assert result.status == "completed"
