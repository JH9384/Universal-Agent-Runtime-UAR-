import uuid
from .contracts import StrategySpec, RunRecord, PipelineContext
from .registry import registry


class Executor:
    def run(self, strategy: StrategySpec, goal) -> RunRecord:
        run = RunRecord(
            run_id=str(uuid.uuid4()),
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            status="running",
        )

        ctx = PipelineContext(goal=goal)

        for skill_name in strategy.ordered_skills:
            try:
                fn = registry.get(skill_name)
                result = fn(ctx)
                ctx.data[skill_name] = result
                ctx.emit("skill_executed", {"skill": skill_name})
                run.outputs.append({skill_name: result})
            except Exception as e:
                run.errors.append(str(e))
                run.status = "failed"
                return run

        # SUM review pass if available
        if "sum_review" in registry.list():
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
