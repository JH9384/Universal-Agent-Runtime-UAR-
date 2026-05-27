import pytest

from uar.core.runtime_dispatch_pipeline import (
    ConstitutionalDispatchPipeline,
    RuntimeDispatchContext,
)
from uar.core.runtime_modes import RuntimeMode


class ReplaySafeContract:
    name = "safe_skill"
    replay_safety = "ReplaySafe"
    side_effect_policy = "NONE"


class ReplayUnsafeContract:
    name = "unsafe_skill"
    replay_safety = "ReplayUnsafe"
    side_effect_policy = "DESTRUCTIVE"


pipeline = ConstitutionalDispatchPipeline()


def executor(value: int) -> int:
    return value * 2


def test_pipeline_allows_safe_execution():
    context = RuntimeDispatchContext(
        runtime_mode=RuntimeMode(name="normal"),
        contract=ReplaySafeContract(),
    )

    result = pipeline.dispatch(executor, context, 4)

    assert result.executed is True
    assert result.result == 8


def test_pipeline_blocks_unsafe_execution():
    context = RuntimeDispatchContext(
        runtime_mode=RuntimeMode(name="deterministic_replay"),
        contract=ReplayUnsafeContract(),
    )

    with pytest.raises(PermissionError):
        pipeline.dispatch(executor, context, 4)
