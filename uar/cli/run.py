import argparse

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.memory.json_store import JsonRunStore

# ensure skills are registered
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa
import uar.skills.graphrag_skills  # noqa


def main():
    parser = argparse.ArgumentParser(description="Run a UAR goal")
    parser.add_argument("--goal", required=True, help="Goal objective text")
    parser.add_argument("--skills", help="Comma-separated skill list")
    parser.add_argument("--input", help="Path for doc ingestion")

    args = parser.parse_args()

    required_skills = args.skills.split(",") if args.skills else []

    goal = GoalSpec(
        id="cli-run",
        user_intent=args.goal,
        objective=args.goal,
        required_skills=required_skills,
        metadata={"input_path": args.input} if args.input else {},
    )

    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy, goal)

    store = JsonRunStore()
    store.append(result)

    print("Run status:", result.status)
    print("Outputs:", result.outputs)


if __name__ == "__main__":
    main()
