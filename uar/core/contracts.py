import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal


SkillMaturity = Literal[
    "stable",
    "beta",
    "experimental",
    "stub",
    "deprecated",
]

SideEffectPolicy = Literal[
    "PURE",
    "LOCAL_WRITE",
    "NETWORK_WRITE",
    "EXTERNAL_MUTATION",
    "DESTRUCTIVE",
]

ReplaySafety = Literal[
    "ReplaySafe",
    "ReplayConditional",
    "ReplayUnsafe",
]

ObservabilityLevel = Literal[
    "minimal",
    "standard",
    "verbose",
]


SKILL_MATURITY_VALUES = {
    "stable",
    "beta",
    "experimental",
    "stub",
    "deprecated",
}

SIDE_EFFECT_POLICY_VALUES = {
    "PURE",
    "LOCAL_WRITE",
    "NETWORK_WRITE",
    "EXTERNAL_MUTATION",
    "DESTRUCTIVE",
}

REPLAY_SAFETY_VALUES = {
    "ReplaySafe",
    "ReplayConditional",
    "ReplayUnsafe",
}

OBSERVABILITY_LEVEL_VALUES = {
    "minimal",
    "standard",
    "verbose",
}


@dataclass(slots=True)
class SkillContract:
    """Runtime governance contract for a registered skill.

    SkillContract is intentionally metadata-first in Phase 2A. It gives the
    registry and executor a stable governance surface before enforcement is
    expanded into scheduling, replay certification, and side-effect policy
    gates.
    """

    name: str
    version: str = "0.1.0"
    maturity: SkillMaturity = "experimental"
    timeout_policy: str = "default"
    retry_policy: str = "default"
    side_effect_policy: SideEffectPolicy = "PURE"
    replay_safety: ReplaySafety = "ReplayConditional"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    failure_modes: List[str] = field(default_factory=list)
    observability_level: ObservabilityLevel = "standard"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Return governance validation errors for this contract."""
        errors: List[str] = []
        if not self.name:
            errors.append("SkillContract.name must be non-empty")
        if self.maturity not in SKILL_MATURITY_VALUES:
            errors.append(f"Invalid skill maturity: {self.maturity}")
        if self.side_effect_policy not in SIDE_EFFECT_POLICY_VALUES:
            errors.append(
                f"Invalid side effect policy: {self.side_effect_policy}"
            )
        if self.replay_safety not in REPLAY_SAFETY_VALUES:
            errors.append(f"Invalid replay safety: {self.replay_safety}")
        if self.observability_level not in OBSERVABILITY_LEVEL_VALUES:
            errors.append(
                f"Invalid observability level: {self.observability_level}"
            )
        if (
            self.replay_safety == "ReplaySafe"
            and self.side_effect_policy != "PURE"
        ):
            errors.append(
                "ReplaySafe skills must declare PURE side_effect_policy"
            )
        return errors

    @property
    def is_executable_by_default(self) -> bool:
        """Whether the skill should execute without explicit override."""
        return self.maturity not in {"deprecated", "stub"}

    @property
    def is_replay_safe(self) -> bool:
        """Whether the skill is safe for deterministic replay certification."""
        return self.replay_safety == "ReplaySafe"


@dataclass
class GoalSpec:
    id: str
    user_intent: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySpec:
    goal_id: str
    ordered_skills: List[str]
    waves: Optional[List[List[str]]] = None


@dataclass(slots=True)
class PipelineContext:
    goal: GoalSpec
    data: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10000  # Prevent unbounded memory growth
    _overflow_file: Any = field(default=None, repr=False)

    def __post_init__(self):
        if os.getenv("UAR_CONTEXT_DISK_OVERFLOW", "").lower() == "true":
            import tempfile

            fd, path = tempfile.mkstemp(suffix=".jsonl")
            os.close(fd)
            object.__setattr__(self, "_overflow_file", open(path, "a"))

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        # Circular buffer: drop oldest events when limit reached
        if len(self.events) >= self._max_events:
            if self._overflow_file is not None:
                import json

                self._overflow_file.write(json.dumps(event, default=str))
                self._overflow_file.write("\n")
            else:
                self.events.pop(0)  # Remove oldest
        self.events.append(event)

    def close(self) -> None:
        if self._overflow_file is not None:
            self._overflow_file.close()
            self._overflow_file = None


@dataclass(slots=True)
class RunRecord:
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List[Any] = field(default_factory=list)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    final_context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    uor_address: Optional[str] = None
    uor_witness: Optional[Dict[str, Any]] = None
