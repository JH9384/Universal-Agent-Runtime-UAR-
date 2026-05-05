import argparse

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.memory.json_store import JsonRunStore
from uar.core.replay import replay_summary

# ensure skills are registered
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa
import uar.skills.graphrag_skills  # noqa
import uar.skills.autonomi_storage  # noqa
import uar.skills.atomic_lang_model  # noqa


def cmd_run(args):
    """Run a UAR goal."""
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


def cmd_list(args):
    """List stored runs."""
    store = JsonRunStore()
    records = store.list_all()
    
    if not records:
        print("No stored runs found.")
        return
    
    print(f"Found {len(records)} stored runs:")
    for i, record in enumerate(records, 1):
        summary = replay_summary(record)
        print(f"{i}. Run ID: {summary['run_id']}")
        print(f"   Goal ID: {summary['goal_id']}")
        print(f"   Status: {summary['status']}")
        print(f"   Skills: {', '.join(summary['skills'])}")
        print(f"   Events: {summary['event_count']}")
        if summary['errors']:
            print(f"   Errors: {', '.join(summary['errors'])}")
        print()


def cmd_replay(args):
    """Replay a stored run."""
    store = JsonRunStore()
    records = store.list_all()
    
    if not records:
        print("No stored runs found.")
        return
    
    if args.index < 1 or args.index > len(records):
        print(f"Invalid index. Must be between 1 and {len(records)}")
        return
    
    record = records[args.index - 1]
    summary = replay_summary(record)
    
    print(f"Replaying run {args.index}:")
    print(f"Run ID: {summary['run_id']}")
    print(f"Goal ID: {summary['goal_id']}")
    print(f"Status: {summary['status']}")
    print(f"Skills: {', '.join(summary['skills'])}")
    print(f"Event count: {summary['event_count']}")
    print(f"Outputs: {summary['outputs']}")
    
    if args.verbose:
        print("\nEvent stream:")
        for event in record.events:
            print(f"  [{event['type']}] {event['skill']}: {event.get('timestamp')}")
            if event.get('error'):
                print(f"    Error: {event['error']}")


def main():
    parser = argparse.ArgumentParser(description="UAR CLI - Universal Agent Runtime")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a UAR goal")
    run_parser.add_argument("--goal", required=True, help="Goal objective text")
    run_parser.add_argument("--skills", help="Comma-separated skill list")
    run_parser.add_argument("--input", help="Path for doc ingestion")

    # List command
    _ = subparsers.add_parser("list", help="List stored runs")

    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a stored run")
    replay_parser.add_argument("--index", type=int, required=True, help="Run index to replay")
    replay_parser.add_argument("--verbose", action="store_true", help="Show full event stream")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "replay":
        cmd_replay(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
