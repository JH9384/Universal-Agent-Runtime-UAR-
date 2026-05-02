from __future__ import annotations

from typing import Any

from uar.core.executor import Executor


class MultiStepEngine:
    def __init__(self):
        self.executor = Executor()

    def run(self, strategy, goal):
        results = []
        context = {}

        for idx, skill in enumerate(strategy.ordered_skills):
            sub_goal = goal
            result = self.executor.run_single(skill, sub_goal, context)

            results.append({
                "step": idx + 1,
                "skill": skill,
                "result": getattr(result, "outputs", None),
                "status": getattr(result, "status", None),
            })

            context[skill] = getattr(result, "outputs", None)

            if getattr(result, "status", None) != "completed":
                break

        return {
            "steps": results,
            "final": results[-1] if results else None,
        }
