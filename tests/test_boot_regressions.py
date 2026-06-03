"""Regression tests for boot/shutdown fixes.

Covers:
- _retention_purge_loop immediate purge (not after 1h sleep)
- wait_for_health total duration cap
- boot_full_stack does not redundantly call boot()
- boot_cli uses single asyncio.run
"""

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRetentionPurgeImmediate:
    """Regression: purge must run before first sleep."""

    @pytest.mark.asyncio
    async def test_purge_runs_before_first_sleep(self):
        from uar.boot import _retention_purge_loop

        sleep_calls = 0
        _real_sleep = asyncio.sleep

        async def _yielding_sleep(*_a, **_kw):
            nonlocal sleep_calls
            sleep_calls += 1
            await _real_sleep(0)  # use real sleep to yield control
            raise asyncio.CancelledError()

        with patch("uar.config.config") as mock_cfg:
            mock_cfg.run_retention_days = 7
            with patch("uar.memory.base_store.get_store") as mock_get_store:
                store = MagicMock()
                store.purge_old_records.return_value = 3
                mock_get_store.return_value = store
                with patch(
                    "uar.boot.asyncio.sleep", side_effect=_yielding_sleep
                ):
                    task = asyncio.create_task(_retention_purge_loop())
                    await task  # Loop breaks on CancelledError from sleep

        assert store.purge_old_records.call_count >= 1
        assert sleep_calls >= 1

    @pytest.mark.asyncio
    async def test_no_purge_when_retention_days_zero(self):
        from uar.boot import _retention_purge_loop

        with patch("uar.config.config") as mock_cfg:
            mock_cfg.run_retention_days = 0
            with patch("uar.memory.base_store.get_store") as mock_get_store:
                store = MagicMock()
                mock_get_store.return_value = store
                await _retention_purge_loop()
        store.purge_old_records.assert_not_called()


class TestWaitForHealthTimeout:
    """Regression: total poll duration must be capped."""

    @pytest.mark.asyncio
    async def test_respects_max_duration(self):
        from uar.boot import wait_for_health

        start = time.monotonic()
        result = await wait_for_health(
            "http://127.0.0.1:59999/nonexistent",
            attempts=1000,
            interval=0.1,
            request_timeout=0.1,
            max_duration=0.3,
        )
        elapsed = time.monotonic() - start

        assert result is False
        assert elapsed < 1.0  # well below 1000 * 0.1 = 100s
        assert elapsed >= 0.15  # at least one attempt + interval

    @pytest.mark.asyncio
    async def test_request_timeout_is_short(self):
        from uar.boot import wait_for_health

        start = time.monotonic()
        result = await wait_for_health(
            "http://127.0.0.1:59999/nonexistent",
            attempts=2,
            interval=0.05,
            request_timeout=0.1,
            max_duration=5.0,
        )
        elapsed = time.monotonic() - start

        assert result is False
        assert elapsed < 0.5  # 2 * 0.1 + overhead, not 2 * 10 = 20s


class TestBootFullStackNoDoubleBoot:
    """Regression: boot_full_stack must not redundantly call boot()."""

    @pytest.mark.asyncio
    async def test_does_not_call_boot(self):
        from uar.boot import boot_full_stack

        with patch("uar.boot.boot") as mock_boot, patch(
            "uar.boot.find_free_port", return_value=9999
        ), patch("uar.boot.ServiceSupervisor") as mock_supervisor:
            supervisor = MagicMock()
            supervisor.start = MagicMock()
            supervisor.health_check = AsyncMock(return_value=True)
            mock_supervisor.return_value = supervisor

            await boot_full_stack(
                api_port=9999, start_web=False, start_dashboard=False
            )

        mock_boot.assert_not_called()


class TestBootCliSingleEventLoop:
    """Regression: boot_cli must use a single asyncio.run call."""

    def test_single_asyncio_run(self):
        from uar.boot import boot_cli

        source = inspect.getsource(boot_cli)
        assert source.count("asyncio.run(") == 1


class TestBootConstantsExistInBootModule:
    """Regression: constants from deleted lifespan module exist in boot."""

    def test_shutdown_sleep_constant(self):
        from uar.boot import SHUTDOWN_SLEEP

        assert isinstance(SHUTDOWN_SLEEP, float)
        assert SHUTDOWN_SLEEP >= 0

    def test_cors_origins_constant(self):
        from uar.boot import CORS_ORIGINS

        assert isinstance(CORS_ORIGINS, list)


class TestServiceSupervisor:
    """ServiceSupervisor lifecycle."""

    def test_is_running_false_for_unknown(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        assert supervisor.is_running("unknown") is False

    def test_start_records_process(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            pid = supervisor.start("svc", ["echo", "hello"])

        assert pid == 12345
        assert supervisor.is_running("svc") is True

    def test_start_same_name_raises(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("dup", ["sleep", "10"])

        with pytest.raises(RuntimeError, match="already running"):
            supervisor.start("dup", ["echo", "x"])

        supervisor.stop_all()

    def test_stop_all_terminates_and_waits(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = None

        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])

        supervisor.stop_all()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()
        assert not supervisor.is_running("svc")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_running(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        ok = await supervisor.health_check("missing", "http://127.0.0.1:1")
        assert ok is False


class TestWaitForHealth:
    """wait_for_health success and failure paths."""

    def test_returns_true_when_healthy(self):
        from uar.boot import wait_for_health

        # Patch urlopen to always return 200
        class _FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            result = asyncio.run(
                wait_for_health(
                    "http://127.0.0.1:99999/health",
                    attempts=1,
                    interval=0.01,
                    request_timeout=0.1,
                )
            )
        assert result is True
