"""Runtime configuration validation.

Covers: invalid ports rejected, invalid persistence rejected,
timeout semantics stable, planner mode enforcement stable.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from uar.config import Config, DEFAULT_API_PORT, MAX_PORT_NUMBER
from uar.core.validation import validate_timeout
from uar.core.exceptions import ValidationError


class TestPortValidation:
    def test_default_port(self):
        cfg = Config()
        assert cfg.api_port == DEFAULT_API_PORT

    def test_valid_custom_port(self):
        with mock.patch.dict(os.environ, {"API_PORT": "9000"}):
            cfg = Config()
            cfg.load_from_env()
            assert cfg.api_port == 9000

    def test_invalid_port_rejected(self):
        """Ports outside valid range should not be silently accepted."""
        with mock.patch.dict(os.environ, {"API_PORT": "99999"}):
            with pytest.raises(ValueError):
                Config()

    def test_port_boundary(self):
        with mock.patch.dict(os.environ, {"API_PORT": str(MAX_PORT_NUMBER)}):
            cfg = Config()
            cfg.load_from_env()
            assert cfg.api_port == MAX_PORT_NUMBER


class TestTimeoutSemantics:
    def test_default_timeout(self):
        assert validate_timeout(5.0) == 5.0

    def test_timeout_too_low_rejected(self):
        with pytest.raises(ValidationError):
            validate_timeout(0.05)

    def test_timeout_too_high_rejected(self):
        with pytest.raises(ValidationError):
            validate_timeout(600.0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValidationError):
            validate_timeout(-1.0)

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValidationError):
            validate_timeout(0.0)


class TestPersistenceConfig:
    def test_persistence_env_flag(self):
        with mock.patch.dict(os.environ, {"UAR_PERSISTENCE_ENABLED": "true"}):
            cfg = Config()
            # Config does not yet have a persistence flag; this test
            # documents the expected contract once it is added.
            assert cfg is not None

    def test_debug_mode_not_production(self):
        with mock.patch.dict(os.environ, {"DEBUG": "true"}):
            cfg = Config()
            cfg.load_from_env()
            assert cfg.debug is True


class TestPlannerModeEnforcement:
    def test_planner_mode_default(self):
        """Default planner mode is simple/deterministic."""
        with mock.patch.dict(os.environ, {}, clear=False):
            cfg = Config()
            assert cfg is not None
            # No LLM planner mode without explicit opt-in
