import functools

from .contracts import GoalSpec, StrategySpec


class SimplePlanner:
    """Naive planner with deterministic skill ordering and caching."""

    def plan(self, goal: GoalSpec) -> StrategySpec:
        # Use cached plan when skills are a plain list of strings
        skills = goal.required_skills or ["section_sum"]
        if isinstance(skills, list) and all(
            isinstance(s, str) for s in skills
        ):
            return self._cached_plan(
                goal_id=goal.id, required_skills=tuple(skills)
            )
        return StrategySpec(goal_id=goal.id, ordered_skills=skills)

    @functools.lru_cache(maxsize=1024)
    def _cached_plan(
        self, goal_id: str, required_skills: tuple
    ) -> StrategySpec:
        """Cache plan by goal id + skills tuple (immutable key)."""
        skills = list(required_skills) or ["section_sum"]
        return StrategySpec(goal_id=goal_id, ordered_skills=skills)
