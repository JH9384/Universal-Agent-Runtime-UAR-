import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from uar.core.contracts import GoalSpec, PipelineContext, RunRecord
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.core.registry import registry
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


def _build_goal(req: RunRequest) -> GoalSpec:
    return GoalSpec(
        id="api-run",
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata={"input_path": req.input_path} if req.input_path else {},
    )


@app.post("/api/uar/run")
def run_goal(req: RunRequest):
    goal = _build_goal(req)
    planner = SimplePlanner()
    strategy = planner.plan(goal)

    executor = Executor()
    result = executor.run(strategy, goal)

    store.append(result)
    return result


@app.post("/api/uar/stream")
def stream_goal(req: RunRequest):
    goal = _build_goal(req)
    strategy = SimplePlanner().plan(goal)

    def emit(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload)}\n\n"

    def generate():
        ctx = PipelineContext(goal=goal)
        run = RunRecord(
            run_id="stream-run",
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            status="running",
        )

        yield emit("start", {"goal": goal.objective, "skills": strategy.ordered_skills})

        for skill_name in strategy.ordered_skills:
            yield emit("skill_start", {"skill": skill_name})
            try:
                fn = registry.get(skill_name)
                result = fn(ctx)
                ctx.data[skill_name] = result
                ctx.emit("skill_executed", {"skill": skill_name})
                run.outputs.append({skill_name: result})
                yield emit("skill_complete", {"skill": skill_name, "result": result})
            except Exception as e:
                run.errors.append(str(e))
                run.status = "failed"
                yield emit("error", {"skill": skill_name, "error": str(e)})
                store.append(run)
                return

        if "sum_review" in registry.list():
            yield emit("skill_start", {"skill": "sum_review"})
            summary = registry.get("sum_review")(ctx)
            run.outputs.append({"sum_review": summary})
            yield emit("skill_complete", {"skill": "sum_review", "result": summary})

        run.status = "completed"
        run.events = ctx.events
        run.final_context = ctx.data
        store.append(run)
        yield emit("complete", {"run": run.__dict__})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/uar/runs")
def list_runs():
    return store.list_records()
