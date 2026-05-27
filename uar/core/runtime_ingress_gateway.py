from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime_gateway import RuntimeGateway, RuntimeGatewayRequest
from .runtime_ingress import RuntimeIngressRecord


@dataclass(slots=True)
class RuntimeIngressResult:
    ingress: RuntimeIngressRecord
    dispatch_result: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingress": self.ingress.to_dict(),
            "dispatch_result": getattr(self.dispatch_result, "to_dict", lambda: self.dispatch_result)(),
        }


class RuntimeIngressGateway:
    """Ingress-level wrapper around RuntimeGateway.

    This is the Phase 3B closure point: every governed execution can be
    represented as an ingress record plus an authority-routed dispatch.
    """

    def __init__(self) -> None:
        self.gateway = RuntimeGateway()

    def run(
        self,
        ingress_id: str,
        request: RuntimeGatewayRequest,
        lineage_continuity: bool = True,
    ) -> RuntimeIngressResult:
        runtime_mode_name = request.context.runtime_mode.name
        dispatch_result = self.gateway.run(request)

        ingress = RuntimeIngressRecord(
            ingress_id=ingress_id,
            runtime_mode=runtime_mode_name,
            replay_safe=True,
            authority_validated=True,
            lineage_continuity=lineage_continuity,
        )

        return RuntimeIngressResult(
            ingress=ingress,
            dispatch_result=dispatch_result,
        )
