"""Runtime governance enforcement helpers.

This module centralizes policy checks so the executor, replay engine, API layer,
and CI scripts can apply the same runtime governance rules without duplicating
logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from .contracts import SkillContract


GovernanceMode = Literal["normal", "deterministic_replay", "production"]


@dataclass(slots=True)
class GovernanceViolation:
    """Single governance policy violation."""

    code: str
    message: str
    skill: Optional[str] = None
    severity: Literal["warning", "error"] = "error"
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class GovernanceDecision:
    """Execution governance decision for a skill."""

    allowed: bool
    skill: str
    mode: GovernanceMode = "normal"
    violations: List[GovernanceViolation] = field(default_factory=list)
    warnings: List[GovernanceViolation] = field(default_factory=list)

    def raise_if_blocked(self) -> None:
        if self.allowed:
            return
        joined = "; ".join(v.message for v in self.violations)
        raise RuntimeError(joined or f"Execution blocked for skill {self.skill}")


def evaluate_skill_execution(
    contract: SkillContract,
    *,
    mode: GovernanceMode = "normal",
    allow_deprecated: bool = False,
    allow_stub: bool = False,
    allow_destructive: bool = False,
) -> GovernanceDecision:
    """Evaluate whether a skill may execute under current governance policy."""
    violations: List[GovernanceViolation] = []
    warnings: List[GovernanceViolation] = []

    for error in contract.validate():
        violations.append(
            GovernanceViolation(
                code="CONTRACT_INVALID",
                message=error,
                skill=contract.name,
            )
        )

    if contract.maturity == "deprecated" and not allow_deprecated:
        violations.append(
            GovernanceViolation(
                code="SKILL_DEPRECATED",
                message=(
                    f"Skill {contract.name} is deprecated and blocked "
                    "without override"
                ),
                skill=contract.name,
            )
        )

    if contract.maturity == "stub" and not allow_stub:
        violations.append(
            GovernanceViolation(
                code="SKILL_STUB",
                message=(
                    f"Skill {contract.name} is a stub and blocked "
                    "without override"
                ),
                skill=contract.name,
            )
        )

    if contract.side_effect_policy == "DESTRUCTIVE" and not allow_destructive:
        violations.append(
            GovernanceViolation(
                code="DESTRUCTIVE_SIDE_EFFECT",
                message=(
                    f"Skill {contract.name} declares DESTRUCTIVE side effects "
                    "and requires explicit override"
                ),
                skill=contract.name,
            )
        )

    if mode == "deterministic_replay":
        if contract.replay_safety == "ReplayUnsafe":
            violations.append(
                GovernanceViolation(
                    code="REPLAY_UNSAFE_SKILL",
                    message=(
                        f"Skill {contract.name} is ReplayUnsafe and cannot "
                        "participate in deterministic replay certification"
                    ),
                    skill=contract.name,
                )
            )
        if contract.side_effect_policy not in {"PURE", "LOCAL_WRITE"}:
            violations.append(
                GovernanceViolation(
                    code="REPLAY_UNSAFE_SIDE_EFFECT",
                    message=(
                        f"Skill {contract.name} declares "
                        f"{contract.side_effect_policy} side effects and is "
                        "not deterministic-replay safe"
                    ),
                    skill=contract.name,
                )
            )

    if mode == "production" and contract.maturity == "experimental":
        warnings.append(
            GovernanceViolation(
                code="EXPERIMENTAL_IN_PRODUCTION",
                message=(
                    f"Skill {contract.name} is experimental in production mode"
                ),
                skill=contract.name,
                severity="warning",
            )
        )

    return GovernanceDecision(
        allowed=not violations,
        skill=contract.name,
        mode=mode,
        violations=violations,
        warnings=warnings,
    )
