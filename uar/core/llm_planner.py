from __future__ import annotations

import json
from typing import List

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.registry import registry
from uar.core.planner import SimplePlanner


def call_ollama(prompt: str) -> str:
    import requests

    try:
        res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": "llama3.2:3b", "prompt": prompt},
            timeout=30,
        )
        data = res.json()
        return data.get("response", "")
    except Exception:
        return ""


class LLMPlanner:
    def plan(self, goal: GoalSpec) -> StrategySpec:
        skills = registry.describe()

        prompt = f"""
You are a planning assistant.

Goal:
{goal.objective}

Available skills:
{json.dumps(skills, indent=2)}

Return ONLY a JSON array of skill names in execution order.
"""

        response = call_ollama(prompt)

        try:
            parsed: List[str] = json.loads(response)
            valid = [s for s in parsed if s in registry.list()]
            if valid:
                return StrategySpec(goal_id=goal.id, ordered_skills=valid)
        except Exception:
            pass

        # fallback to deterministic planner
        return SimplePlanner().plan(goal)
