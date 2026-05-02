from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.memory.json_store import JsonRunStore
import uar.skills.section_sum  # register


def test_pipeline_with_memory(tmp_path):
    store_path = tmp_path / "runs.jsonl"
    store = JsonRunStore(str(store_path))

    goal = GoalSpec(id="2", user_intent="test", objective="test")
    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy, goal)

    store.append(result)

    records = store.list_records()
    assert len(records) == 1
    assert records[0]["status"] == "completed"
