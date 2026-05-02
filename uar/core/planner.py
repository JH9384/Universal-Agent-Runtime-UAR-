from .contracts import GoalSpec, StrategySpec


class SimplePlanner:
    def plan(self, goal: GoalSpec) -> StrategySpec:
        # naive: use required skills or fallback
        skills = goal.required_skills or ["section_sum"]
        return StrategySpec(goal_id=goal.id, ordered_skills=skills)
