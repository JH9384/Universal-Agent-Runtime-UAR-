"""Tests for FastAPI lifespan handler.

Covers config constants and helper functions.
"""

from unittest.mock import patch

from uar.api.lifespan import (
    SHUTDOWN_SLEEP,
    create_lifespan,
)


class TestConfigConstants:
    """Lifespan configuration constants."""

    def test_shutdown_sleep(self):
        assert isinstance(SHUTDOWN_SLEEP, float)
        assert SHUTDOWN_SLEEP >= 0

    def test_cors_origins_prod(self):
        env = {"ENVIRONMENT": "production", "CORS_ORIGINS": "https://app.com"}
        with patch.dict("os.environ", env, clear=True):
            # Need to reimport to pick up env change
            import importlib
            from uar.api import lifespan
            importlib.reload(lifespan)
            assert lifespan.CORS_ORIGINS == ["https://app.com"]


class TestCreateLifespan:
    """Lifespan factory."""

    def test_returns_callable(self):
        counter = type("Counter", (), {"count": 0})()
        lifespan = create_lifespan(counter)
        assert callable(lifespan)
