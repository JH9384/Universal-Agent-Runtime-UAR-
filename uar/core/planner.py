"""Planning primitives for UAR.

UAR is deterministic-first. Adaptive planning may be added behind an
explicit opt-in gate, but the default planning path must remain stable,
inspectable, and replayable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import GoalSpec, StrategySpec

PlannerMode = Literal["simple", "recipe", "llm"]


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime-level planner configuration.

    The default configuration is intentionally conservative: use the
    deterministic planner and disallow LLM planning unless explicitly enabled.
    """

    planner_mode: PlannerMode = "simple"
    allow_llm: bool = False


class SimplePlanner:
    """Deterministic skill-order planner.

    Uses goal.required_skills when present, otherwise falls back to the
    canonical section summarization skill.
    """

    def plan(self, goal: GoalSpec) -> StrategySpec:
        skills = goal.required_skills or ["section_sum"]
        return StrategySpec(goal_id=goal.id, ordered_skills=skills)


class RecipePlanner(SimplePlanner):
    """Structured planner placeholder for recipe-aware orchestration.

    v1 intentionally preserves SimplePlanner behavior until recipes are wired
    into a dedicated planning contract. This keeps the router stable without
    inventing implicit semantics.
    """


class LLMPlanner:
    """Opt-in adaptive planner placeholder.

    The class exists so routing, config, and conformance can be tested before
    any provider-specific LLM behavior is allowed into the execution path.
    """

    def plan(self, goal: GoalSpec) -> StrategySpec:
        raise RuntimeError(
            "LLMPlanner is not implemented. Use planner_mode='simple' or "
            "planner_mode='recipe', or provide an explicit implementation."
        )


class PlannerRouter:
    """Fail-closed router for selecting a planner implementation."""

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()

    def route(self) -> SimplePlanner | RecipePlanner | LLMPlanner:
        mode = self.config.planner_mode

        if mode == "simple":
            return SimplePlanner()
        if mode == "recipe":
            return RecipePlanner()
        if mode == "llm":
            if not self.config.allow_llm:
                raise ValueError(
                    "LLM planner requested but allow_llm is false. "
                    "Set allow_llm=true to opt in explicitly."
                )
            return LLMPlanner()

        # Defensive fail-closed branch for runtime-loaded configs that bypass
        # static PlannerMode typing.
        raise ValueError(f"Unsupported planner mode: {mode!r}")

    def plan(self, goal: GoalSpec) -> StrategySpec:
        return self.route().plan(goal)
