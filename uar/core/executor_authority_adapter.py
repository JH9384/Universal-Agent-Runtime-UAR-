"""Executor authority adapter.

Hard-gates executor dispatch behind runtime governance checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .execution_authority import authorize_execution
from .policy_engine import PolicyDecision
from .runtime_modes import RuntimeMode


@dataclass(slots=True)
class DispatchResult:
    executed: bool
    result: Any = None
    reason: str | None = None


def guarded_dispatch(
    executor: Callable[..., Any],
    runtime_mode: RuntimeMode,
    policy_decision: PolicyDecision,
    *args: Any,
    **kwargs: Any,
) -> DispatchResult:
    authority = authorize_execution(runtime_mode, policy_decision)

    if not authority.allowed:
        return DispatchResult(
            executed=False,
            result=None,
            reason="; ".join(authority.reasons),
        )

    result = executor(*args, **kwargs)

    return DispatchResult(
        executed=True,
        result=result,
        reason=None,
    )
