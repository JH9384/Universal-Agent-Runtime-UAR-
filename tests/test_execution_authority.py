from uar.core.execution_authority import authorize_execution
from uar.core.policy_engine import PolicyDecision
from uar.core.runtime_modes import RuntimeMode


def test_execution_authority_accepts_valid_execution():
    runtime_mode = RuntimeMode(name="standard", level=1)
    policy = PolicyDecision(allowed=True, reasons=[])

    result = authorize_execution(runtime_mode, policy)

    assert result.allowed is True
    assert result.runtime_mode == "standard"


def test_execution_authority_rejects_invalid_policy():
    runtime_mode = RuntimeMode(name="standard", level=1)
    policy = PolicyDecision(allowed=False, reasons=["policy violation"])

    result = authorize_execution(runtime_mode, policy)

    assert result.allowed is False
    assert "policy violation" in result.reasons


def test_execution_authority_rejects_disabled_runtime():
    runtime_mode = RuntimeMode(name="disabled", level=0)
    policy = PolicyDecision(allowed=True, reasons=[])

    result = authorize_execution(runtime_mode, policy)

    assert result.allowed is False
    assert "runtime mode disabled" in result.reasons
