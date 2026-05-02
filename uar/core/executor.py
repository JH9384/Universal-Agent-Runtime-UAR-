import uuid
import signal
from .contracts import StrategySpec, RunRecord, PipelineContext
from .registry import registry

class TimeoutException(Exception):
    pass

def _timeout_handler(signum, frame):
    raise TimeoutException("Skill execution timed out")

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
            try:
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(timeout_seconds)

                fn = registry.get(skill_name)
                result = fn(ctx)

                signal.alarm(0)

                ctx.data[skill_name] = result
                ctx.emit("skill_executed", {"skill": skill_name})
                run.outputs.append({skill_name: result})

            except Exception as e:
                run.errors.append(str(e))
                run.status = "failed"
                signal.alarm(0)
                return run

        if "sum_review" in registry.list() and "sum_review" not in strategy.ordered_skills:
            try:
                sum_fn = registry.get("sum_review")
                summary = sum_fn(ctx)
                run.outputs.append({"sum_review": summary})
            except Exception as e:
                run.errors.append(str(e))

        run.status = "completed"
        run.events = ctx.events
        run.final_context = ctx.data

        return run
