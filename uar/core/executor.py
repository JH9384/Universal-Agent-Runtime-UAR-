import concurrent.futures
import uuid

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


class Executor:
    def run(self, strategy: StrategySpec, goal, timeout_seconds=5) -> RunRecord:
        run = RunRecord(
            run_id=str(uuid.uuid4()),
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            status="running",
        )

        ctx = PipelineContext(goal=goal)

        for skill_name in strategy.ordered_skills:
            ctx.emit("skill_start", {"skill": skill_name})
            try:
                fn = registry.get(skill_name)
                result = _run_with_timeout(fn, ctx, timeout_seconds)

                ctx.data[skill_name] = result
                ctx.emit("skill_complete", {"skill": skill_name})
                run.outputs.append({skill_name: result})

            except Exception as e:
                ctx.emit("skill_failed", {"skill": skill_name, "error": str(e)})
                run.errors.append(str(e))
                run.status = "failed"
                run.events = ctx.events
                run.final_context = ctx.data
                return run

        if "sum_review" in registry.list() and "sum_review" not in strategy.ordered_skills:
            try:
                sum_fn = registry.get("sum_review")
                summary = _run_with_timeout(sum_fn, ctx, timeout_seconds)
                run.outputs.append({"sum_review": summary})
            except Exception as e:
                run.errors.append(str(e))

        run.status = "completed"
        run.events = ctx.events
        run.final_context = ctx.data

        return run
