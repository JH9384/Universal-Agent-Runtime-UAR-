from uar.core.runtime_dispatch_pipeline import (
    ConstitutionalDispatchPipeline,
    RuntimeDispatchContext,
)
from uar.core.runtime_modes import RuntimeMode


class SafeContract:
    name = "safe"
    replay_safety = "ReplaySafe"
    side_effect_policy = "NONE"


pipeline = ConstitutionalDispatchPipeline()


def runtime_executor(value: int) -> int:
    return value + 1


def test_constitutional_execution_chain():
    context = RuntimeDispatchContext(
        runtime_mode=RuntimeMode(name="normal"),
        contract=SafeContract(),
    )

    result = pipeline.dispatch(runtime_executor, context, 10)

    assert result.executed is True
    assert result.result == 11
