"""Runtime mode authority primitives.

Runtime modes define the operational topology for UAR execution. They are
intentionally small and serializable so they can be included in run
certificates, policy decisions, replay authority reports, and CI artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal


RuntimeModeName = Literal[
    "normal",
    "deterministic_replay",
    "production",
    "research",
    "simulation",
    "forensic",
    "audit",
    "sandbox",
]


@dataclass(frozen=True, slots=True)
class RuntimeMode:
    """Execution topology mode for runtime authority decisions."""

    name: RuntimeModeName = "normal"
    require_replay_safe: bool = False
    allow_network_write: bool = True
    allow_external_mutation: bool = True
    allow_destructive: bool = False
    require_lineage: bool = False
    require_certification: bool = False
    max_parallelism: int | None = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "require_replay_safe": self.require_replay_safe,
            "allow_network_write": self.allow_network_write,
            "allow_external_mutation": self.allow_external_mutation,
            "allow_destructive": self.allow_destructive,
            "require_lineage": self.require_lineage,
            "require_certification": self.require_certification,
            "max_parallelism": self.max_parallelism,
            "metadata": dict(self.metadata),
        }


RUNTIME_MODES: Dict[RuntimeModeName, RuntimeMode] = {
    "normal": RuntimeMode(name="normal"),
    "deterministic_replay": RuntimeMode(
        name="deterministic_replay",
        require_replay_safe=True,
        allow_network_write=False,
        allow_external_mutation=False,
        allow_destructive=False,
        require_lineage=True,
        require_certification=True,
        max_parallelism=1,
    ),
    "production": RuntimeMode(
        name="production",
        allow_destructive=False,
        require_lineage=True,
        require_certification=True,
    ),
    "research": RuntimeMode(name="research"),
    "simulation": RuntimeMode(
        name="simulation",
        allow_network_write=False,
        allow_external_mutation=False,
        allow_destructive=False,
        require_lineage=True,
    ),
    "forensic": RuntimeMode(
        name="forensic",
        require_replay_safe=True,
        allow_network_write=False,
        allow_external_mutation=False,
        allow_destructive=False,
        require_lineage=True,
        require_certification=True,
        max_parallelism=1,
    ),
    "audit": RuntimeMode(
        name="audit",
        allow_network_write=False,
        allow_external_mutation=False,
        allow_destructive=False,
        require_lineage=True,
        require_certification=True,
    ),
    "sandbox": RuntimeMode(
        name="sandbox",
        allow_external_mutation=False,
        allow_destructive=False,
        require_lineage=True,
    ),
}


def get_runtime_mode(name: str | None) -> RuntimeMode:
    """Resolve a runtime mode by name, defaulting to normal."""
    if not name:
        return RUNTIME_MODES["normal"]
    if name not in RUNTIME_MODES:
        raise ValueError(f"Unknown runtime mode: {name}")
    return RUNTIME_MODES[name]  # type: ignore[index]
