"""Constitutional runtime dispatch pipeline.

This module wires runtime mode, policy evaluation, and execution authority
into a single mandatory dispatch path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .execution_authority import authorize_execution
from .executor_authority_adapter import DispatchResult
from .policy_engine import DEFAULT_RUNTIME_POLICY
from .runtime_modes import RuntimeMode


@dataclass(slots=True)
class RuntimeDispatchContext:
    runtime_mode: RuntimeMode
    contract: Any


class ConstitutionalDispatchPipeline:
    """Mandatory authority pipeline for executor dispatch."""

    def dispatch(
        self,
        executor: Callable[..., Any],
        context: RuntimeDispatchContext,
        *args: Any,
        **kwargs: Any,
    ) -> DispatchResult:
        policy_decision = DEFAULT_RUNTIME_POLICY.evaluate(
            context.contract,
            context.runtime_mode,
        )

        authority = authorize_execution(
            context.runtime_mode,
            policy_decision,
        )

        authority.raise_if_blocked()

        result = executor(*args, **kwargs)

        return DispatchResult(
            executed=True,
            result=result,
            reason=None,
        )
