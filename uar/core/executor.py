import concurrent.futures
import time
import uuid
from typing import Iterator

from .contracts import PipelineContext, RunRecord, StrategySpec
from .registry import registry


class TimeoutException(Exception):
    pass


def _run_with_timeout(fn, ctx, timeout_seconds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, ctx)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutException("Skill execution timed out") from exc


def _event(event_type: str, run_id: str, goal_id: str, skill=None, payload=None, error=None):
    return {
        "schema_version": "uar.event.v1",
        "type": event_type,
        "run_id": run_id,
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": time.time(),
        "payload": payload or {},
        "error": error,
    }


class Executor:
    def iter_events(self, strategy: StrategySpec, goal, timeout_seconds=5) -> Iterator[dict]:
        run_id = str(uuid.uuid4())
        ctx = PipelineContext(goal=goal)
        outputs = []
        errors = []

        yield _event(
            "start",
            run_id,
            strategy.goal_id,
            payload={"goal": goal.objective, "skills": strategy.ordered_skills},
        )

        for skill_name in strategy.ordered_skills:
            yield _event("skill_start", run_id, strategy.goal_id, skill=skill_name)
            try:
                fn = registry.get(skill_name)
                result = _run_with_timeout(fn, ctx, timeout_seconds)
                ctx.data[skill_name] = result
                outputs.append({skill_name: result})
                yield _event(
                    "skill_complete",
                    run_id,
                    strategy.goal_id,
                    skill=skill_name,
                    payload={"result": result},
                )
            except Exception as e:
                message = str(e)
                errors.append(message)
                yield _event("skill_failed", run_id, strategy.goal_id, skill=skill_name, error=message)
                yield _event(
                    "complete",
                    run_id,
                    strategy.goal_id,
                    payload={
                        "status": "failed",
                        "outputs": outputs,
                        "errors": errors,
                        "final_context": ctx.data,
                    },
                )
                return

        if "sum_review" in registry.list() and "sum_review" not in strategy.ordered_skills:
            skill_name = "sum_review"
            yield _event("skill_start", run_id, strategy.goal_id, skill=skill_name)
            try:
                summary = _run_with_timeout(registry.get(skill_name), ctx, timeout_seconds)
                outputs.append({skill_name: summary})
                yield _event(
                    "skill_complete",
                    run_id,
                    strategy.goal_id,
                    skill=skill_name,
                    payload={"result": summary},
                )
            except Exception as e:
                errors.append(str(e))

        yield _event(
            "complete",
            run_id,
            strategy.goal_id,
            payload={
                "status": "completed" if not errors else "failed",
                "outputs": outputs,
                "errors": errors,
                "final_context": ctx.data,
            },
        )

    def run(self, strategy: StrategySpec, goal, timeout_seconds=5) -> RunRecord:
        events = list(self.iter_events(strategy, goal, timeout_seconds=timeout_seconds))
        start_event = events[0]
        complete_event = events[-1]
        payload = complete_event.get("payload", {})

        return RunRecord(
            run_id=start_event["run_id"],
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            outputs=payload.get("outputs", []),
            status=payload.get("status", "failed"),
            errors=payload.get("errors", []),
            events=events,
            final_context=payload.get("final_context", {}),
        )
