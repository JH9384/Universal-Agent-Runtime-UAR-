from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.memory.json_store import JsonRunStore

# register skills
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa

app = FastAPI(title="UAR API")
store = JsonRunStore()


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None


@app.post("/api/uar/run")
def run_goal(req: RunRequest):
    goal = GoalSpec(
        id="api-run",
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata={"input_path": req.input_path} if req.input_path else {},
    )

    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy, goal)

    store.append(result)
    return result


@app.get("/api/uar/runs")
def list_runs():
    return store.list_records()
