"""Execution authority enforcement.

Central authority gate ensuring runtime execution cannot proceed
without governance and policy validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .policy_engine import PolicyDecision
from .runtime_modes import RuntimeMode


@dataclass(slots=True)
class ExecutionAuthorityResult:
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


def authorize_execution(
    runtime_mode: RuntimeMode,
    policy_decision: PolicyDecision,
) -> ExecutionAuthorityResult:
    reasons: List[str] = []

    if not policy_decision.allowed:
        reasons.extend(policy_decision.reasons)

    if runtime_mode.name.lower() == "disabled":
        reasons.append("runtime mode disabled")

    allowed = len(reasons) == 0

    return ExecutionAuthorityResult(
        allowed=allowed,
        runtime_mode=runtime_mode.name,
        reasons=reasons,
        metadata={
            "policy_allowed": policy_decision.allowed,
            "runtime_level": runtime_mode.level,
        },
    )
