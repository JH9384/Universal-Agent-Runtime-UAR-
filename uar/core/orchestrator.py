from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

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
    waves: list[list[str]] = field(default_factory=list)

    def ordered_skills(self) -> list[str]:
        return [node.skill for node in self.nodes]

    def to_strategy(self) -> StrategySpec:
        return StrategySpec(
            goal_id=self.goal_id, ordered_skills=self.ordered_skills()
        )

    def to_graph(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "waves": self.waves,
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


SkillDeps = Dict[str, Dict[str, List[str]]]


def compute_parallel_waves(
    skills: List[str],
    dependency_map: Optional[SkillDeps] = None,
) -> List[List[str]]:
    """Compute waves of skills that can run in parallel.

    Uses a simple read/write dependency model.  Each skill may declare
    ``reads`` (context keys it consumes) and ``writes`` (context keys it
    produces).  Skills in the same wave must not have conflicting
    writes, and a skill may only read keys written by skills in
    earlier waves.

    When *dependency_map* is ``None`` or a skill has no entry, the
    skill is assumed to read nothing and write its own skill name.
    """
    if not skills:
        return []

    # Normalise dependency map
    deps: SkillDeps = {}
    for skill in skills:
        entry = (dependency_map or {}).get(skill, {})
        deps[skill] = {
            "reads": list(entry.get("reads", [])),
            "writes": list(entry.get("writes", [skill])),
        }

    # Greedy wave construction (preserves input order within waves)
    remaining = list(skills)
    waves: List[List[str]] = []
    written: Set[str] = set()

    while remaining:
        wave: List[str] = []
        wave_writes: Set[str] = set()

        for skill in remaining[:]:
            skill_deps = deps[skill]
            reads = set(skill_deps["reads"])
            writes = set(skill_deps["writes"])

            # A skill can join this wave if:
            # 1. All keys it reads have already been written (by prior
            #    waves or by skills in the same wave that appear before
            #    it — but we simplify and only check prior waves).
            # 2. It does not write any key that another skill in this
            #    wave writes.
            if reads.issubset(written) and not (writes & wave_writes):
                wave.append(skill)
                wave_writes.update(writes)

        if not wave:
            # Dependency deadlock — break cycle by forcing the first
            # remaining skill into its own wave.
            wave = [remaining[0]]
            skill = remaining[0]
            wave_writes.update(deps[skill]["writes"])

        waves.append(wave)
        for skill in wave:
            remaining.remove(skill)
            written.update(deps[skill]["writes"])

    return waves


def build_orchestration_plan(
    strategy: StrategySpec,
    dependency_map: Optional[SkillDeps] = None,
) -> OrchestrationPlan:
    """Build an orchestration plan from a strategy.

    If *dependency_map* is provided, the plan is built as a DAG and
    ``waves`` contains the parallel execution groups.  Otherwise the
    plan falls back to a linear chain.
    """
    nodes: list[OrchestrationNode] = []

    if dependency_map:
        # Build DAG-aware plan with proper parallel waves
        waves = compute_parallel_waves(
            strategy.ordered_skills, dependency_map
        )
        # Build node lookup and assign dependencies based on waves
        node_by_skill: Dict[str, OrchestrationNode] = {}
        for index, skill in enumerate(strategy.ordered_skills):
            if skill not in registry.list():
                metadata = {"registered": False}
            else:
                metadata = {"registered": True}

            node_id = f"skill-{index + 1}-{skill}"
            node = OrchestrationNode(
                id=node_id,
                skill=skill,
                depends_on=[],
                metadata=metadata,
            )
            nodes.append(node)
            node_by_skill[skill] = node

        # Set dependencies: each skill depends on all skills in
        # previous waves that write keys it reads.
        written_by: Dict[str, str] = {}
        for wave in waves:
            for skill in wave:
                skill_deps = dependency_map.get(skill, {})
                reads = set(skill_deps.get("reads", []))
                depends = []
                for key in reads:
                    if key in written_by:
                        dep_skill = written_by[key]
                        dep_node = node_by_skill[dep_skill]
                        if dep_node.id not in depends:
                            depends.append(dep_node.id)
                node_by_skill[skill].depends_on = depends
            # Record writes after the wave is processed
            for skill in wave:
                skill_deps = dependency_map.get(skill, {})
                writes = set(skill_deps.get("writes", [skill]))
                for key in writes:
                    written_by[key] = skill

        return OrchestrationPlan(
            goal_id=strategy.goal_id,
            nodes=nodes,
            mode="dag",
            waves=waves,
        )

    # Fallback: linear chain
    previous_id: str | None = None
    for index, skill in enumerate(strategy.ordered_skills):
        if skill not in registry.list():
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

    return OrchestrationPlan(
        goal_id=strategy.goal_id,
        nodes=nodes,
        mode="sequential",
        waves=[[s] for s in strategy.ordered_skills],
    )
