from uar.core.executor import Executor
from uar.core.llm_planner import LLMPlanner
from uar.core.planner import SimplePlanner
import os

MAX_ITER = int(os.getenv("UAR_AGENT_MAX_ITERATIONS", "3"))


def evaluate(result):
    # simple heuristic evaluator
    if not result or result.get("status") != "completed":
        return False
    return True


class AgentLoop:
    def run(self, goal):
        planner = LLMPlanner()
        executor = Executor()

        for i in range(MAX_ITER):
            strategy = planner.plan(goal)
            result = executor.run(strategy, goal)

            if evaluate(result.__dict__):
                return result

        # fallback final deterministic pass
        strategy = SimplePlanner().plan(goal)
        return executor.run(strategy, goal)
