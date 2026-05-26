from uar.core.executor_authority_adapter import guarded_dispatch
from uar.core.policy_engine import PolicyDecision
from uar.core.runtime_modes import RuntimeMode


def sample_executor(value: int) -> int:
    return value * 2


def test_guarded_dispatch_executes_when_allowed():
    result = guarded_dispatch(
        sample_executor,
        RuntimeMode(name="standard", level=1),
        PolicyDecision(allowed=True, reasons=[]),
        5,
    )

    assert result.executed is True
    assert result.result == 10


def test_guarded_dispatch_blocks_when_denied():
    result = guarded_dispatch(
        sample_executor,
        RuntimeMode(name="standard", level=1),
        PolicyDecision(allowed=False, reasons=["blocked"]),
        5,
    )

    assert result.executed is False
    assert result.result is None
    assert "blocked" in result.reason
