from __future__ import annotations

import json
import os
from typing import Any, List

import httpx

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.registry import registry
from uar.core.planner import SimplePlanner


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_PLANNER_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_PLANNER_TIMEOUT_SECONDS", "10"))
MAX_PLANNER_SKILLS = int(os.getenv("UAR_MAX_PLANNER_SKILLS", "5"))


def call_ollama(prompt: str) -> str:
    try:
        res = httpx.post(
            f"{OLLAMA_HOST.rstrip('/')}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_PLANNER_TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        data = res.json()
        return data.get("response", "")
    except Exception:
        return ""


class LLMPlanner:
    def plan(self, goal: GoalSpec, feedback: dict[str, Any] | None = None) -> StrategySpec:
        skills = registry.describe()
        feedback_block = ""
        if feedback:
            feedback_block = f"""
Previous evaluation feedback:
{json.dumps(feedback, indent=2)}

Adapt the next skill plan to address the failed reasons, but still use only listed skills.
"""

        prompt = f"""
You are a planning assistant for UAR.

Goal:
{goal.objective}

Available skills:
{json.dumps(skills, indent=2)}

{feedback_block}
Rules:
- Return ONLY a JSON array of skill names in execution order.
- Use only listed skills.
- Do not include explanations.
- Keep the plan short.
"""

        response = call_ollama(prompt)

        try:
            parsed: List[str] = json.loads(response)
            valid = [s for s in parsed if s in registry.list()]
            valid = valid[:MAX_PLANNER_SKILLS]
            if valid:
                return StrategySpec(goal_id=goal.id, ordered_skills=valid)
        except Exception:
            pass

        return SimplePlanner().plan(goal)
