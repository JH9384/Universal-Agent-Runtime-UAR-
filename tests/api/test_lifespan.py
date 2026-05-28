"""Tests for FastAPI lifespan handler.

Covers config constants and helper functions.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

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


class TestLifespanStartup:
    """Lifespan startup path."""

    def _patches(self):
        return {
            "docs._cleanup": patch(
                "uar.api.routers.docs._cleanup_orphaned_temp_files"
            ),
            "docs._library_dir": patch(
                "uar.api.routers.docs._library_dir", return_value="/tmp/lib"
            ),
            "objects.seed": patch(
                "uar.objects.seed_standard_runtimes"
            ),
            "objects.get_store": patch(
                "uar.objects.get_default_store", return_value=MagicMock()
            ),
            "plugin.load": patch(
                "uar.skills.plugin.load_plugins"
            ),
            "tracing.setup": patch(
                "uar.api.tracing.setup_fastapi_tracing"
            ),
            "config.validate": patch(
                "uar.config.validate_environment", return_value=[]
            ),
            "config.docker": patch(
                "uar.config.validate_docker_environment",
                return_value=[],
            ),
            "config_advanced.validate": patch(
                "uar.config_advanced.validate_advanced_config",
                return_value={},
            ),
            "config_advanced.log": patch(
                "uar.config_advanced.log_validation_results"
            ),
        }

    @pytest.mark.asyncio
    async def test_startup_completes(self):
        from fastapi import FastAPI

        app = FastAPI()
        counter = type("Counter", (), {"count": 0})()
        lifespan = create_lifespan(counter)

        patches = self._patches()
        with ExitStack() as stack:
            for p in patches.values():
                stack.enter_context(p)
            async with lifespan(app):
                pass  # Startup + immediate shutdown

    @pytest.mark.asyncio
    async def test_startup_validation_fails(self):
        from fastapi import FastAPI

        app = FastAPI()
        counter = type("Counter", (), {"count": 0})()
        lifespan = create_lifespan(counter)

        patches = self._patches()
        with ExitStack() as stack:
            mocks = {}
            for key, p in patches.items():
                mocks[key] = stack.enter_context(p)
            # Make validation fail
            mocks["config.validate"].return_value = ["missing env"]
            with pytest.raises(RuntimeError, match="startup validation"):
                async with lifespan(app):
                    pass


class TestLifespanShutdown:
    """Lifespan shutdown path."""

    def _patches(self):
        return {
            "docs._cleanup": patch(
                "uar.api.routers.docs._cleanup_orphaned_temp_files"
            ),
            "docs._library_dir": patch(
                "uar.api.routers.docs._library_dir", return_value="/tmp/lib"
            ),
            "objects.seed": patch(
                "uar.objects.seed_standard_runtimes"
            ),
            "objects.get_store": patch(
                "uar.objects.get_default_store", return_value=MagicMock()
            ),
            "plugin.load": patch(
                "uar.skills.plugin.load_plugins"
            ),
            "tracing.setup": patch(
                "uar.api.tracing.setup_fastapi_tracing"
            ),
            "config.validate": patch(
                "uar.config.validate_environment", return_value=[]
            ),
            "config.docker": patch(
                "uar.config.validate_docker_environment",
                return_value=[],
            ),
            "config_advanced.validate": patch(
                "uar.config_advanced.validate_advanced_config",
                return_value={},
            ),
            "config_advanced.log": patch(
                "uar.config_advanced.log_validation_results"
            ),
            "metrics.get_collector": patch(
                "uar.api.metrics.get_metrics_collector",
                return_value=MagicMock(),
            ),
            "postgres.shutdown": patch(
                "uar.memory.postgres_store._shutdown_postgres_pool"
            ),
            "http.close": patch(
                "uar.core.http_client.close_all_sessions"
            ),
        }

    @pytest.mark.asyncio
    async def test_shutdown_drains_ws(self):
        from fastapi import FastAPI

        app = FastAPI()
        counter = type("Counter", (), {"count": 0})()
        lifespan = create_lifespan(counter)

        patches = self._patches()
        with ExitStack() as stack:
            for p in patches.values():
                stack.enter_context(p)
            with patch("uar.api.lifespan.SHUTDOWN_SLEEP", 0.1):
                async with lifespan(app):
                    pass

    @pytest.mark.asyncio
    async def test_shutdown_with_active_ws(self):
        from fastapi import FastAPI

        app = FastAPI()
        counter = type("Counter", (), {"count": 2})()
        lifespan = create_lifespan(counter)

        patches = self._patches()
        with ExitStack() as stack:
            for p in patches.values():
                stack.enter_context(p)
            with patch("uar.api.lifespan.SHUTDOWN_SLEEP", 0.1):
                with patch("uar.api.lifespan.asyncio.sleep"):
                    async with lifespan(app):
                        pass
