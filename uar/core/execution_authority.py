"""Execution authority enforcement.

Central authority gate ensuring runtime execution cannot proceed without
runtime-mode and policy validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .policy_engine import PolicyDecision
from .runtime_modes import RuntimeMode


@dataclass(slots=True)
class ExecutionAuthorityResult:
    """Serializable authorization result for executor dispatch."""

    allowed: bool
    runtime_mode: str
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "runtime_mode": self.runtime_mode,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }

    def raise_if_blocked(self) -> None:
        if self.allowed:
            return
        message = "; ".join(self.reasons) or "Execution authority blocked dispatch"
        raise PermissionError(message)


def authorize_execution(
    runtime_mode: RuntimeMode,
    policy_decision: PolicyDecision,
) -> ExecutionAuthorityResult:
    """Combine runtime-mode and policy results into a dispatch decision."""
    reasons: List[str] = []

    if not policy_decision.allowed:
        reasons.extend(policy_decision.violations)

    allowed = len(reasons) == 0

    return ExecutionAuthorityResult(
        allowed=allowed,
        runtime_mode=runtime_mode.name,
        reasons=reasons,
        metadata={
            "policy_allowed": policy_decision.allowed,
            "policy_name": policy_decision.policy_name,
            "skill": policy_decision.skill,
            "require_replay_safe": runtime_mode.require_replay_safe,
            "require_lineage": runtime_mode.require_lineage,
            "require_certification": runtime_mode.require_certification,
        },
    )
