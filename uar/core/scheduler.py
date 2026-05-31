"""DAG-aware skill scheduler for UAR.

Replaces the greedy wave construction in ``orchestrator.py`` with a
proper topological sort (Kahn's algorithm) that respects explicit
dependencies, read/write context keys, and context-modifying barriers.
"""

from typing import Dict, List, Optional, Set, Tuple

from .exceptions import ValidationError
from .registry import SkillRegistry


# Skills that modify shared context and must never run in parallel.
CONTEXT_MODIFYING_SKILLS = {"doc_ingest", "graphrag_index"}


class CircularDependencyError(ValidationError):
    """Raised when skill dependencies form a cycle."""

    def __init__(self, cycle: List[str]) -> None:
        self.cycle = cycle
        super().__init__(
            f"Circular dependency detected: {' -> '.join(cycle)}",
            field="skills",
        )


def _build_dependency_graph(
    skills: List[str],
    registry: SkillRegistry,
    explicit_deps: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Build incoming and outgoing edge maps for the skill DAG.

    Edges are derived from:
    1. Explicit ``depends_on`` from recipe definitions.
    2. Read-after-write context key relationships from skill metadata.
    3. Context-modifying barriers (serialized after all prior skills).
    """
    incoming: Dict[str, Set[str]] = {s: set() for s in skills}
    outgoing: Dict[str, Set[str]] = {s: set() for s in skills}

    # Index of who writes what
    written_by: Dict[str, str] = {}
    skill_writes: Dict[str, Set[str]] = {}

    for skill in skills:
        meta = registry.get_metadata(skill)
        writes = set(meta.get("writes", [skill]))
        skill_writes[skill] = writes
        # Register writes — if multiple skills write the same key,
        # the earlier one in the list wins as the producer.
        for key in writes:
            if key not in written_by:
                written_by[key] = skill

    # Build edges from read/write relationships
    for skill in skills:
        meta = registry.get_metadata(skill)
        reads = set(meta.get("reads", []))
        for key in reads:
            if key in written_by and written_by[key] != skill:
                producer = written_by[key]
                incoming[skill].add(producer)
                outgoing[producer].add(skill)

    # Add explicit dependencies
    if explicit_deps:
        for skill, deps in explicit_deps.items():
            if skill not in incoming:
                continue
            for dep in deps:
                if dep in incoming and dep != skill:
                    incoming[skill].add(dep)
                    outgoing[dep].add(skill)

    # Context-modifying skills must wait for all prior skills
    prior: List[str] = []
    for skill in skills:
        if skill in CONTEXT_MODIFYING_SKILLS:
            for p in prior:
                if p != skill:
                    incoming[skill].add(p)
                    outgoing[p].add(skill)
        prior.append(skill)

    return incoming, outgoing


def schedule(
    skills: List[str],
    registry: SkillRegistry,
    explicit_deps: Optional[Dict[str, List[str]]] = None,
) -> List[List[str]]:
    """Return waves of skills that can run in parallel.

    Uses Kahn's algorithm for topological sort, grouping skills with
    in-degree zero into the same wave when possible.

    Args:
        skills: Ordered list of skill names to execute.
        registry: Skill registry for metadata lookups.
        explicit_deps: Optional mapping of skill -> list of dependencies.

    Returns:
        List of skill groups (waves) where each group can run in parallel.

    Raises:
        CircularDependencyError: If dependencies form a cycle.
    """
    if not skills:
        return []

    incoming, outgoing = _build_dependency_graph(
        skills, registry, explicit_deps
    )

    # Compute in-degree
    in_degree = {s: len(incoming[s]) for s in skills}

    # Initialize queue with zero-in-degree nodes, preserving input order
    queue = [s for s in skills if in_degree[s] == 0]

    waves: List[List[str]] = []
    visited: Set[str] = set()

    while queue:
        # All zero-in-degree nodes form one wave
        wave = list(queue)
        waves.append(wave)
        visited.update(wave)
        queue = []

        for skill in wave:
            for neighbor in outgoing[skill]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0 and neighbor not in visited:
                    queue.append(neighbor)

    if len(visited) != len(skills):
        # Find the cycle for a helpful error message
        remaining = [s for s in skills if s not in visited]
        raise CircularDependencyError(remaining + [remaining[0]])

    return waves
