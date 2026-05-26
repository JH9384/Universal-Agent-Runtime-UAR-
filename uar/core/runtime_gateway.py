from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .runtime_dispatch_pipeline import ConstitutionalDispatchPipeline
from .runtime_dispatch_pipeline import RuntimeDispatchContext


@dataclass(slots=True)
class RuntimeGatewayRequest:
    executor: Callable[..., Any]
    context: RuntimeDispatchContext
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None


class RuntimeGateway:
    """Governed runtime execution gateway."""

    def __init__(self) -> None:
        self.pipeline = ConstitutionalDispatchPipeline()

    def run(self, request: RuntimeGatewayRequest):
        return self.pipeline.dispatch(
            request.executor,
            request.context,
            *(request.args or ()),
            **(request.kwargs or {}),
        )
