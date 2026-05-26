from uar.core.runtime_gateway import RuntimeGatewayRequest
from uar.core.runtime_ingress_gateway import RuntimeIngressGateway
from uar.core.runtime_dispatch_pipeline import RuntimeDispatchContext
from uar.core.runtime_modes import RuntimeMode


class SafeContract:
    name = "safe"
    replay_safety = "ReplaySafe"
    side_effect_policy = "NONE"


def executor(value: int) -> int:
    return value + 5


def test_runtime_ingress_gateway_tracks_continuity():
    gateway = RuntimeIngressGateway()

    request = RuntimeGatewayRequest(
        executor=executor,
        context=RuntimeDispatchContext(
            runtime_mode=RuntimeMode(name="deterministic_replay"),
            contract=SafeContract(),
        ),
        args=(7,),
    )

    result = gateway.run(
        ingress_id="ingress-007",
        request=request,
        lineage_continuity=True,
    )

    payload = result.to_dict()

    assert payload["ingress"]["authority_validated"] is True
    assert payload["ingress"]["lineage_continuity"] is True
