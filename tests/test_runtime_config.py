import pytest

from uar.core.config import RuntimeConfig



def test_default_runtime_config_is_valid():
    config = RuntimeConfig()

    config.validate()

    assert config.planner_mode == "simple"
    assert config.allow_llm is False



def test_llm_mode_requires_explicit_opt_in():
    config = RuntimeConfig(planner_mode="llm", allow_llm=False)

    with pytest.raises(ValueError, match="explicit opt-in"):
        config.validate()



def test_invalid_port_is_rejected():
    config = RuntimeConfig(api_port=70000)

    with pytest.raises(ValueError, match="between 1 and 65535"):
        config.validate()



def test_invalid_timeout_is_rejected():
    config = RuntimeConfig(default_timeout_seconds=0)

    with pytest.raises(ValueError, match="must be positive"):
        config.validate()



def test_invalid_persistence_mode_is_rejected():
    config = RuntimeConfig(persistence_mode="bad")

    with pytest.raises(ValueError, match="Unsupported persistence mode"):
        config.validate()
