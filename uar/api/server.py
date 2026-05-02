import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.replay import run_record_from_events
from uar.core.orchestrator import build_orchestration_plan
from uar.memory.json_store import JsonRunStore

# register skills
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa

app = FastAPI(title="UAR API")
store = JsonRunStore()


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None


def _build_goal(req: RunRequest) -> GoalSpec:
    return GoalSpec(
        id="api-run",
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata={"input_path": req.input_path} if req.input_path else {},
    )


def _run_goal_impl(req: RunRequest):
    goal = _build_goal(req)
    planner = SimplePlanner()
    strategy = planner.plan(goal)

    from uar.core.executor import Executor

    executor = Executor()
    result = executor.run(strategy, goal)

    store.append(result)
    return result


def _stream_goal_impl(req: RunRequest):
    goal = _build_goal(req)
    strategy = SimplePlanner().plan(goal)
    plan = build_orchestration_plan(strategy)

    from uar.core.executor import Executor

    executor = Executor()

    def emit(event: dict) -> str:
        return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

    def generate():
        events = []

        yield emit({
            "schema_version": "uar.event.v1",
            "type": "orchestration_plan",
            "run_id": "pending",
            "goal_id": strategy.goal_id,
            "skill": None,
            "timestamp": 0,
            "payload": {"graph": plan.to_graph()},
            "error": None,
        })

        for event in executor.iter_events(strategy, goal):
            events.append(event)
            yield emit(event)

        record = run_record_from_events(events, strategy.ordered_skills)
        store.append(record)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/uar/run")
def run_goal(req: RunRequest):
    return _run_goal_impl(req)


@app.post("/api/v1/uar/run")
def run_goal_v1(req: RunRequest):
    return _run_goal_impl(req)


@app.post("/api/uar/stream")
def stream_goal(req: RunRequest):
    return _stream_goal_impl(req)


@app.post("/api/v1/uar/stream")
def stream_goal_v1(req: RunRequest):
    return _stream_goal_impl(req)


@app.get("/api/uar/runs")
def list_runs():
    return store.list_records()


@app.get("/api/v1/uar/runs")
def list_runs_v1():
    return store.list_records()
