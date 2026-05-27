import pytest

from uar.core.runtime_gateway import RuntimeGateway
from uar.core.runtime_gateway import RuntimeGatewayRequest
from uar.core.runtime_dispatch_pipeline import RuntimeDispatchContext
from uar.core.runtime_modes import RuntimeMode


class SafeContract:
    name = "safe"
    replay_safety = "ReplaySafe"
    side_effect_policy = "NONE"


class UnsafeContract:
    name = "unsafe"
    replay_safety = "ReplayUnsafe"
    side_effect_policy = "DESTRUCTIVE"


runtime_gateway = RuntimeGateway()


def executor(value: int) -> int:
    return value * 3


def test_runtime_gateway_allows_safe_execution():
    request = RuntimeGatewayRequest(
        executor=executor,
        context=RuntimeDispatchContext(
            runtime_mode=RuntimeMode(name="normal"),
            contract=SafeContract(),
        ),
        args=(3,),
    )

    result = runtime_gateway.run(request)

    assert result.executed is True
    assert result.result == 9


def test_runtime_gateway_blocks_unsafe_execution():
    request = RuntimeGatewayRequest(
        executor=executor,
        context=RuntimeDispatchContext(
            runtime_mode=RuntimeMode(name="deterministic_replay"),
            contract=UnsafeContract(),
        ),
        args=(3,),
    )

    with pytest.raises(PermissionError):
        runtime_gateway.run(request)
