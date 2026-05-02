from dataclasses import dataclass, field
from typing import Any

from uar.core.contracts import StrategySpec
from uar.core.registry import registry


@dataclass
class OrchestrationNode:
    id: str
    skill: str
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationPlan:
    goal_id: str
    nodes: list[OrchestrationNode]
    mode: str = "sequential"

    def ordered_skills(self) -> list[str]:
        return [node.skill for node in self.nodes]

    def to_strategy(self) -> StrategySpec:
        return StrategySpec(goal_id=self.goal_id, ordered_skills=self.ordered_skills())

    def to_graph(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "nodes": [
                {
                    "id": node.id,
                    "skill": node.skill,
                    "depends_on": node.depends_on,
                    "metadata": node.metadata,
                }
                for node in self.nodes
            ],
            "edges": [
                {"from": dependency, "to": node.id}
                for node in self.nodes
                for dependency in node.depends_on
            ],
        }


def build_orchestration_plan(strategy: StrategySpec) -> OrchestrationPlan:
    nodes: list[OrchestrationNode] = []
    previous_id: str | None = None

    for index, skill in enumerate(strategy.ordered_skills):
        if skill not in registry.list():
            # Keep missing skills visible to the planner/executor instead of hiding them.
            metadata = {"registered": False}
        else:
            metadata = {"registered": True}

        node_id = f"skill-{index + 1}-{skill}"
        nodes.append(
            OrchestrationNode(
                id=node_id,
                skill=skill,
                depends_on=[previous_id] if previous_id else [],
                metadata=metadata,
            )
        )
        previous_id = node_id

    return OrchestrationPlan(goal_id=strategy.goal_id, nodes=nodes)
