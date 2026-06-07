"""Tests for uar.boot lifespan and background tasks."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from uar.boot import (
    _retention_purge_loop,
    BootContext,
    create_lifespan,
    shutdown,
)


@pytest.mark.asyncio
async def test_retention_purge_loop_cancelled():
    task = asyncio.create_task(_retention_purge_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_retention_purge_loop_negative_retention():
    with patch("uar.config.config") as mock_cfg:
        mock_cfg.run_retention_days = -1
        await _retention_purge_loop()


@pytest.mark.asyncio
async def test_retention_purge_loop_exception_handling():
    """Exceptions in purge_old_records must be caught and loop continues."""
    _real_sleep = asyncio.sleep

    async def _yielding_sleep(*_a, **_kw):
        await _real_sleep(0)
        raise asyncio.CancelledError()

    with patch("uar.config.config") as mock_cfg:
        mock_cfg.run_retention_days = 7
        with patch("uar.memory.base_store.get_store") as mock_get_store:
            store = MagicMock()
            # First call raises, second call succeeds, then sleep breaks
            store.purge_old_records.side_effect = [RuntimeError("boom"), 0]
            mock_get_store.return_value = store
            with patch(
                "uar.boot.asyncio.sleep", side_effect=_yielding_sleep
            ):
                task = asyncio.create_task(_retention_purge_loop())
                await task

    assert store.purge_old_records.call_count == 2


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown():
    ws_counter = MagicMock()
    ws_counter.count = 0
    ctx = BootContext(ws_conn_counter=ws_counter)
    lifespan = create_lifespan(ctx)

    from fastapi import FastAPI

    app = FastAPI(lifespan=lifespan)
    with patch.dict("sys.modules", {"opentelemetry": None}):
        metrics_patch = patch(
            "uar.api.metrics.get_metrics_collector",
            return_value=MagicMock(),
        )
        with metrics_patch:
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    async with lifespan(app):
                        pass


class TestBootContext:
    """BootContext dataclass behavior."""

    def test_accepts_custom_ws_counter(self):
        counter = MagicMock()
        ctx = BootContext(ws_conn_counter=counter)
        assert ctx.ws_conn_counter is counter
        assert ctx.purge_task is None

    def test_default_values(self):
        ctx = BootContext(ws_conn_counter=MagicMock())
        assert ctx.purge_task is None
        assert isinstance(ctx.started_at, float)
        assert ctx.plugins_loaded == {}
        assert ctx.temp_files_cleaned == 0


class TestShutdown:
    """Shutdown sequence coverage."""

    @pytest.mark.asyncio
    async def test_cancels_purge_task(self):
        ws_counter = MagicMock()
        ws_counter.count = 0
        ctx = BootContext(ws_conn_counter=ws_counter)
        ctx.purge_task = asyncio.create_task(asyncio.sleep(3600))

        with patch("uar.api.metrics.get_metrics_collector") as mock_get:
            mock_get.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    await shutdown(ctx)

        assert ctx.purge_task.cancelled()

    @pytest.mark.asyncio
    async def test_gracefully_handles_missing_dependencies(self):
        ws_counter = MagicMock()
        ws_counter.count = 0
        ctx = BootContext(ws_conn_counter=ws_counter)

        with patch("uar.api.metrics.get_metrics_collector") as mock_get:
            mock_get.side_effect = ImportError("no metrics")
            with patch(
                "uar.memory.postgres_store._shutdown_postgres_pool"
            ) as mock_pg:
                mock_pg.side_effect = RuntimeError("pg down")
                with patch(
                    "uar.core.http_client.close_all_sessions"
                ) as mock_http:
                    mock_http.side_effect = RuntimeError("http down")
                    # Should not raise despite multiple failures
                    await shutdown(ctx)


class TestFindFreePort:
    """Port-discovery safety."""

    def test_exhaustion_raises_runtime_error(self):
        """If every port from start to MAX_PORT_NUMBER is bound, raise."""
        from uar.boot import find_free_port, MAX_PORT_NUMBER

        with patch("uar.boot.is_port_bound", return_value=True):
            with pytest.raises(
                RuntimeError, match="No free port found"
            ):
                find_free_port(start=MAX_PORT_NUMBER - 1)

    def test_returns_first_free_port(self):
        """Returns the first unbound port at or after start."""
        from uar.boot import find_free_port

        call_count = 0

        def _fake_bound(port, _host):
            nonlocal call_count
            call_count += 1
            return port < 9000

        with patch("uar.boot.is_port_bound", side_effect=_fake_bound):
            result = find_free_port(start=8999)
        assert result == 9000


class TestBootFullStackHealthFailures:
    """boot_full_stack must propagate health-check failures."""

    @pytest.mark.asyncio
    async def test_web_health_failure_raises(self):
        """If web health check fails, boot_full_stack must raise."""
        from uar.boot import boot_full_stack

        # Mock prerequisites and port binding so we reach the web check
        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.is_port_bound", return_value=False):
                with patch("subprocess.Popen") as mock_popen:
                    mock_proc = MagicMock()
                    mock_proc.poll.return_value = None
                    mock_proc.pid = 12345
                    mock_popen.return_value = mock_proc
                    with patch(
                        "uar.boot.wait_for_health"
                    ) as mock_wait:
                        # API health passes, web health fails
                        mock_wait.side_effect = [True, False]
                        with pytest.raises(
                            RuntimeError,
                            match="Web UI health check failed",
                        ):
                            await boot_full_stack(
                                start_web=True,
                                start_dashboard=False,
                                open_browser_ui=False,
                            )

    @pytest.mark.asyncio
    async def test_dashboard_health_failure_raises(self):
        """If dashboard health check fails, boot_full_stack must raise."""
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.is_port_bound", return_value=False):
                with patch("subprocess.Popen") as mock_popen:
                    mock_proc = MagicMock()
                    mock_proc.poll.return_value = None
                    mock_proc.pid = 12345
                    mock_popen.return_value = mock_proc
                    with patch(
                        "uar.boot.wait_for_health"
                    ) as mock_wait:
                        # API passes, web passes, dashboard fails
                        mock_wait.side_effect = [True, True, False]
                        with pytest.raises(
                            RuntimeError,
                            match="Dashboard health check failed",
                        ):
                            await boot_full_stack(
                                start_web=True,
                                start_dashboard=True,
                                open_browser_ui=False,
                            )
