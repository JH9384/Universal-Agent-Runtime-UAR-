"""Runtime policy engine primitives for Phase 3A.

The policy layer converts runtime governance into deterministic, serializable
policy decisions. It is intentionally small at first so it can be wired into the
executor without changing orchestration behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .contracts import SkillContract
from .runtime_modes import RuntimeMode


@dataclass(slots=True)
class PolicyDecision:
    """Serializable result of evaluating a runtime policy."""

    allowed: bool
    policy_name: str
    skill: str
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "allowed": self.allowed,
            "policy_name": self.policy_name,
            "skill": self.skill,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def raise_if_blocked(self) -> None:
        if self.allowed:
            return
        message = "; ".join(self.violations) or "Runtime policy blocked execution"
        raise RuntimeError(message)


@dataclass(slots=True)
class RuntimePolicy:
    """Runtime policy configuration.

    Phase 3A starts with policy fields that map directly to the existing
    SkillContract and RuntimeMode surfaces.
    """

    name: str = "default-runtime-policy"
    require_replay_safe: bool = False
    forbid_destructive_skills: bool = True
    deny_network_in_certified_modes: bool = True
    deny_external_mutation_in_certified_modes: bool = True
    require_lineage_tracking: bool = False

    def evaluate(self, contract: SkillContract, mode: RuntimeMode) -> PolicyDecision:
        violations: List[str] = []
        warnings: List[str] = []

        if self.require_replay_safe and contract.replay_safety != "ReplaySafe":
            violations.append(f"{contract.name} is not ReplaySafe")

        if mode.require_replay_safe and contract.replay_safety == "ReplayUnsafe":
            violations.append(f"{contract.name} is ReplayUnsafe in {mode.name} mode")

        if self.forbid_destructive_skills and contract.side_effect_policy == "DESTRUCTIVE":
            violations.append(f"{contract.name} declares DESTRUCTIVE side effects")

        if not mode.allow_network_write and contract.side_effect_policy == "NETWORK_WRITE":
            violations.append(f"{contract.name} declares NETWORK_WRITE in {mode.name} mode")

        if (
            not mode.allow_external_mutation
            and contract.side_effect_policy == "EXTERNAL_MUTATION"
        ):
            violations.append(
                f"{contract.name} declares EXTERNAL_MUTATION in {mode.name} mode"
            )

        if not mode.allow_destructive and contract.side_effect_policy == "DESTRUCTIVE":
            violations.append(f"{contract.name} is destructive in {mode.name} mode")

        if mode.require_lineage or self.require_lineage_tracking:
            warnings.append("lineage tracking required")

        return PolicyDecision(
            allowed=not violations,
            policy_name=self.name,
            skill=contract.name,
            violations=violations,
            warnings=warnings,
            metadata={"runtime_mode": mode.name},
        )


DEFAULT_RUNTIME_POLICY = RuntimePolicy()
