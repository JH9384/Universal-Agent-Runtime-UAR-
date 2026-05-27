import pytest

from uar.core.governed_executor import GovernedExecutor


def test_governed_executor_authorizes_execution():
    executor = GovernedExecutor()

    result = executor.execute("runtime_task")

    assert result == "executed:runtime_task"


def test_governed_executor_rejects_invalid_execution():
    executor = GovernedExecutor()

    with pytest.raises(PermissionError):
        executor.execute("")
