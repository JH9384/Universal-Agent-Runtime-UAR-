import json
import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.replay import run_record_from_events
from uar.core.orchestrator import build_orchestration_plan
from uar.memory.json_store import JsonRunStore
from uar.skills.adapter import load_skill_directory

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


class ExternalSkillRequest(BaseModel):
    path: Optional[str] = None


def _build_goal(req: RunRequest) -> GoalSpec:
    return GoalSpec(
        id="api-run",
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata={"input_path": req.input_path} if req.input_path else {},
    )


def _default_skill_dir() -> str:
    return os.getenv("UAR_EXTERNAL_SKILLS_DIR", os.path.expanduser("~/claude-skills"))


@app.get("/api/uar/external-skills")
def list_external_skills(path: Optional[str] = None):
    """List safe imported external skills as UAR template data.

    External skills are treated as data only. This endpoint does not execute skill
    instructions or grant any additional runtime capabilities.
    """
    skill_dir = path or _default_skill_dir()
    return {
        "path": skill_dir,
        "templates": load_skill_directory(skill_dir),
    }


@app.post("/api/uar/external-skills/preview")
def preview_external_skills(req: ExternalSkillRequest):
    skill_dir = req.path or _default_skill_dir()
    return {
        "path": skill_dir,
        "templates": load_skill_directory(skill_dir),
    }


@app.post("/api/uar/run")
def run_goal(req: RunRequest):
    goal = _build_goal(req)
    planner = SimplePlanner()
    strategy = planner.plan(goal)

    from uar.core.executor import Executor

    executor = Executor()
    result = executor.run(strategy, goal)

    store.append(result)
    return result


@app.post("/api/uar/stream")
def stream_goal(req: RunRequest):
    goal = _build_goal(req)
    strategy = SimplePlanner().plan(goal)

    plan = build_orchestration_plan(strategy)

    from uar.core.executor import Executor

    executor = Executor()

    def emit(event: dict) -> str:
        return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

    def generate():
        events = []

        # emit orchestration graph first
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


@app.get("/api/uar/runs")
def list_runs():
    return store.list_records()
