import uuid
from .contracts import StrategySpec, RunRecord
from .registry import registry


class Executor:
    def run(self, strategy: StrategySpec) -> RunRecord:
        run = RunRecord(
            run_id=str(uuid.uuid4()),
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            status="running",
        )

        for skill_name in strategy.ordered_skills:
            try:
                fn = registry.get(skill_name)
                result = fn()
                run.outputs.append({skill_name: result})
            except Exception as e:
                run.errors.append(str(e))
                run.status = "failed"
                return run

        run.status = "completed"
        return run
