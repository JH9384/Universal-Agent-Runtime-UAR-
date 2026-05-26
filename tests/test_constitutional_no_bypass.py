import pytest

from uar.core.runtime_dispatch_pipeline import (
    ConstitutionalDispatchPipeline,
    RuntimeDispatchContext,
)
from uar.core.runtime_modes import RuntimeMode


class DangerousContract:
    name = "dangerous"
    replay_safety = "ReplayUnsafe"
    side_effect_policy = "DESTRUCTIVE"


pipeline = ConstitutionalDispatchPipeline()


def forbidden_executor() -> str:
    return "should_not_execute"


def test_constitutional_pipeline_prevents_bypass():
    context = RuntimeDispatchContext(
        runtime_mode=RuntimeMode(name="deterministic_replay"),
        contract=DangerousContract(),
    )

    with pytest.raises(PermissionError):
        pipeline.dispatch(forbidden_executor, context)
