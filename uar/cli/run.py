import argparse

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.memory.json_store import JsonRunStore

# ensure skills are registered
import uar.skills.section_sum  # noqa


def main():
    parser = argparse.ArgumentParser(description="Run a UAR goal")
    parser.add_argument("--goal", required=True, help="Goal objective text")

    args = parser.parse_args()

    goal = GoalSpec(
        id="cli-run",
        user_intent=args.goal,
        objective=args.goal,
    )

    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy)

    store = JsonRunStore()
    store.append(result)

    print("Run status:", result.status)
    print("Outputs:", result.outputs)


if __name__ == "__main__":
    main()
