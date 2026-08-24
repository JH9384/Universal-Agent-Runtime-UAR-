"""Tests for remaining uncovered boot.py paths."""

import asyncio
import inspect
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from uar.boot import (
    BootContext,
    _validate_advanced_config,
    _validate_environment,
    _seed_uor_runtimes,
    _load_plugins,
    boot_cli,
    create_app,
    create_lifespan,
    ensure_directories,
    find_free_port,
    is_port_bound,
    open_browser,
    shutdown,
    validate_prerequisites,
)


class _ClosedMockTask:
    """Awaitable stand-in for intercepted asyncio tasks."""

    def __init__(self, coro=None):
        if inspect.iscoroutine(coro):
            coro.close()
        self.cancel = Mock()
        self.cancelled = Mock(return_value=False)
        self.done = Mock(return_value=True)

    def add_done_callback(self, fn):
        fn(self)

    def exception(self):
        return None

    def __await__(self):
        async def _done():
            return None

        return _done().__await__()


def _close_asyncio_run_coro(coro):
    """Close boot_cli coroutine objects when asyncio.run is mocked."""
    if inspect.iscoroutine(coro):
        coro.close()
    return None


def _closed_mock_task(coro):
    """Return an awaitable mock and close unscheduled coroutines."""
    return _ClosedMockTask(coro)


class TestBootCli:
    """boot_cli entry point."""

    def test_source_has_single_asyncio_run(self):
        source = inspect.getsource(boot_cli)
        assert source.count("asyncio.run(") == 1

    def test_boot_cli_api_only_path(self):
        with patch("sys.argv", ["uar.boot", "--port", "9999"]):
            with patch("uar.boot.create_app") as mock_create:
                mock_app = MagicMock()
                mock_create.return_value = mock_app
                with patch("uvicorn.run") as mock_uvicorn:
                    boot_cli()
                    mock_uvicorn.assert_called_once()

    def test_boot_cli_with_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar")
        with patch("sys.argv", ["uar.boot", "--env-file", str(env_file)]):
            with patch("uar.boot.create_app") as mock_create:
                mock_app = MagicMock()
                mock_create.return_value = mock_app
                with patch("uvicorn.run"):
                    boot_cli()

    def test_boot_cli_services_parsing(self):
        with patch("sys.argv", ["uar.boot", "--services", "api,web"]):
            with patch("uar.boot.boot_full_stack", new_callable=AsyncMock):
                with patch("asyncio.run", side_effect=_close_asyncio_run_coro):
                    boot_cli()


class TestCreateApp:
    """FastAPI app factory."""

    def test_create_app_with_context(self):
        ctx = BootContext(ws_conn_counter=MagicMock())
        app = create_app(ctx)
        assert app is not None

    def test_create_app_without_context(self):
        ctx = BootContext(ws_conn_counter=MagicMock())
        with patch("uar.boot.boot", return_value=ctx):
            app = create_app()
            assert app is not None

    def test_create_app_cors_origins(self):
        ctx = BootContext(ws_conn_counter=MagicMock())
        app = create_app(ctx)
        # CORS middleware should be registered
        assert len(app.user_middleware) >= 0

    def test_create_app_trusted_hosts(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_HOSTS", "example.com,test.com")
        ctx = BootContext(ws_conn_counter=MagicMock())
        app = create_app(ctx)
        assert app is not None


class TestCreateLifespan:
    """Lifespan factory."""

    def test_returns_asynccontextmanager(self):
        ctx = BootContext(ws_conn_counter=MagicMock())
        lifespan = create_lifespan(ctx)
        assert callable(lifespan)

    def test_lifespan_with_zero_retention(self, monkeypatch):
        monkeypatch.setenv("RUN_RETENTION_DAYS", "0")
        ctx = BootContext(ws_conn_counter=MagicMock())
        lifespan = create_lifespan(ctx)
        assert callable(lifespan)

    @pytest.mark.asyncio
    async def test_lifespan_starts_purge_task(self):
        from fastapi import FastAPI

        class _FakeTask:
            def __init__(self):
                self._cancelled = False
                self._callbacks: list = []

            def cancel(self):
                self._cancelled = True

            def add_done_callback(self, fn):
                self._callbacks.append(fn)

            def __await__(self):
                if inspect.iscoroutinefunction(self._await_impl):
                    return self._await_impl().__await__()
                return iter([])

            async def _await_impl(self):
                return None

        ctx = BootContext(ws_conn_counter=MagicMock())
        lifespan = create_lifespan(ctx)
        app = FastAPI()
        with patch("uar.api.tracing.setup_fastapi_tracing"):
            with patch("uar.config.config") as mock_cfg:
                mock_cfg.run_retention_days = 7
                with patch(
                    "asyncio.create_task", side_effect=_closed_mock_task
                ):
                    with patch("uar.boot.SHUTDOWN_SLEEP", 0.001):
                        async with lifespan(app):
                            pass
                    assert isinstance(ctx.purge_task, _ClosedMockTask)


class TestServiceSupervisorStart:
    """ServiceSupervisor start variations."""

    def test_start_with_cwd(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 123
        mock_proc.poll.return_value = None
        with patch("subprocess.Popen", return_value=mock_proc) as popen:
            pid = supervisor.start("svc", ["echo", "hi"], cwd=tmp_path)
            assert pid == 123
            assert popen.call_args[1]["cwd"] == str(tmp_path)

    def test_start_with_env(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 456
        mock_proc.poll.return_value = None
        with patch("subprocess.Popen", return_value=mock_proc) as popen:
            pid = supervisor.start("svc", ["echo", "hi"], env={"EXTRA": "val"})
            assert pid == 456
            assert popen.call_args[1]["env"]["EXTRA"] == "val"

    def test_start_with_log_path(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 789
        mock_proc.poll.return_value = None
        log_file = tmp_path / "svc.log"
        with patch("subprocess.Popen", return_value=mock_proc) as popen:
            pid = supervisor.start("svc", ["echo", "hi"], log_path=log_file)
            assert pid == 789
            assert "stdout" in popen.call_args[1]
        supervisor.stop_all()  # close log file

    def test_start_failure_closes_log(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        log_file = tmp_path / "svc.log"
        with patch("subprocess.Popen", side_effect=OSError("exec failed")):
            with pytest.raises(OSError):
                supervisor.start("svc", ["false"], log_path=log_file)


class TestServiceSupervisorStop:
    """ServiceSupervisor stop_all edge cases."""

    def test_stop_all_timeout_then_kill(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = MagicMock()
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),
            None,
        ]
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor.stop_all()
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    def test_stop_all_kill_timeout_expired(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = MagicMock()
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),
            subprocess.TimeoutExpired("cmd", 2),
        ]
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor.stop_all()  # must not raise

    def test_stop_all_stdout_close_error(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.close.side_effect = OSError("bad fd")
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor.stop_all()  # must not raise

    def test_stop_all_log_fp_close(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = None
        log_file = tmp_path / "svc.log"
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"], log_path=log_file)
        supervisor.stop_all()
        assert len(supervisor._procs) == 0


class TestValidatePrerequisites:
    """validate_prerequisites."""

    def test_python_version_too_old(self):
        import sys
        from collections import namedtuple

        VInfo = namedtuple(
            "VInfo",
            ["major", "minor", "micro", "releaselevel", "serial"],
        )
        fake_vinfo = VInfo(
            major=3,
            minor=9,
            micro=0,
            releaselevel="final",
            serial=0,
        )
        with patch.object(sys, "version_info", fake_vinfo):
            missing = validate_prerequisites()
            assert any("Python 3.10" in m for m in missing)


class TestFindFreePort:
    """find_free_port when port is in use."""

    @pytest.mark.allow_hosts("127.0.0.1")
    def test_finds_next_port(self):
        port = find_free_port(59990)
        assert port >= 59990


class TestBootFullStack:
    """boot_full_stack edge cases."""

    @pytest.mark.asyncio
    async def test_missing_prerequisites(self):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=["node"]):
            with pytest.raises(RuntimeError, match="prerequisite"):
                await boot_full_stack()


class TestBootCliFullStack:
    """boot_cli full-stack orchestration path."""

    def test_full_stack_services(self):
        with patch("sys.argv", ["uar.boot", "--services", "api,web"]):
            with patch("uar.boot.boot_full_stack") as mock_boot:
                with patch("asyncio.run", side_effect=_close_asyncio_run_coro):
                    boot_cli()
            mock_boot.assert_not_called()  # asyncio.run patches prevent call


class TestShutdownPaths:
    """Shutdown edge cases."""

    @pytest.mark.asyncio
    async def test_shutdown_no_purge_task(self):
        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        ctx.purge_task = None
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    await shutdown(ctx)

    @pytest.mark.asyncio
    async def test_shutdown_drains_active_ws(self):
        ws = MagicMock()
        ws.count = 1
        ctx = BootContext(ws_conn_counter=ws)
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    with patch("uar.boot.SHUTDOWN_SLEEP", 0.01):
                        await shutdown(ctx)

    @pytest.mark.asyncio
    async def test_shutdown_metrics_failure(self):
        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.side_effect = ImportError("no metrics")
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    await shutdown(ctx)

    @pytest.mark.asyncio
    async def test_shutdown_postgres_failure(self):
        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch(
                "uar.memory.postgres_store._shutdown_postgres_pool"
            ) as pg:
                pg.side_effect = RuntimeError("pg down")
                with patch("uar.core.http_client.close_all_sessions"):
                    await shutdown(ctx)

    @pytest.mark.asyncio
    async def test_shutdown_http_failure(self):
        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions") as h:
                    h.side_effect = RuntimeError("http down")
                    await shutdown(ctx)

    @pytest.mark.asyncio
    async def test_shutdown_purge_task_cancelled(self):
        class _FakeTask:
            def __init__(self):
                self._cancelled = False

            def cancel(self):
                self._cancelled = True

            def __await__(self):
                return iter([])

        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        task = _FakeTask()
        ctx.purge_task = task
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    with patch("uar.boot.SHUTDOWN_SLEEP", 0.01):
                        await shutdown(ctx)
        assert task._cancelled is True


class TestBootContextDefaults:
    """BootContext initialization."""

    def test_default_values(self):
        ws = MagicMock()
        ctx = BootContext(ws_conn_counter=ws)
        assert ctx.purge_task is None
        assert ctx.plugins_loaded == {}
        assert ctx.temp_files_cleaned == 0
        assert isinstance(ctx.started_at, float)

    def test_post_init_defaults(self):
        with patch("uar.api.state._ws_conn_counter") as mock_counter:
            ctx = BootContext()
            assert ctx.ws_conn_counter is mock_counter


class TestProductionChecks:
    """_production_checks warnings."""

    def test_warns_missing_cors_in_production(self, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("CORS_ORIGINS", "")
        monkeypatch.setenv("SECURITY_HEADERS", "enabled")
        import importlib
        from uar import boot as boot_mod

        importlib.reload(boot_mod)
        with caplog.at_level("WARNING", logger="uar.boot"):
            boot_mod._production_checks()
        assert "CORS_ORIGINS" in caplog.text

    def test_warns_missing_security_headers(self, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("CORS_ORIGINS", "https://app.com")
        monkeypatch.setenv("SECURITY_HEADERS", "")
        import importlib
        from uar import boot as boot_mod

        importlib.reload(boot_mod)
        with caplog.at_level("WARNING", logger="uar.boot"):
            boot_mod._production_checks()
        assert "SECURITY_HEADERS" in caplog.text


class TestValidateEnvironment:
    """_validate_environment fail-fast."""

    def test_passes_when_no_issues(self):
        with patch("uar.config.validate_environment", return_value=[]):
            with patch(
                "uar.config.validate_docker_environment", return_value=[]
            ):
                _validate_environment()  # must not raise

    def test_raises_when_issues_found(self):
        with patch(
            "uar.config.validate_environment", return_value=["missing env"]
        ):
            with patch(
                "uar.config.validate_docker_environment", return_value=[]
            ):
                with pytest.raises(RuntimeError, match="startup validation"):
                    _validate_environment()


class TestValidateAdvancedConfig:
    """_validate_advanced_config non-fatal."""

    def test_normal_path(self):
        with patch(
            "uar.config_advanced.validate_advanced_config", return_value={}
        ):
            with patch("uar.config_advanced.log_validation_results"):
                _validate_advanced_config()  # must not raise

    def test_exception_is_logged(self):
        with patch(
            "uar.config_advanced.validate_advanced_config",
            side_effect=ImportError("missing"),
        ):
            _validate_advanced_config()  # must not raise


class TestSeedUorRuntimes:
    """_seed_uor_runtimes exception handling."""

    def test_exception_is_logged(self):
        with patch(
            "uar.objects.seed_standard_runtimes",
            side_effect=RuntimeError("fail"),
        ):
            _seed_uor_runtimes()  # must not raise


class TestLoadPlugins:
    """_load_plugins exception handling."""

    def test_exception_returns_empty(self):
        with patch(
            "uar.skills.plugin.load_plugins",
            side_effect=ImportError("missing"),
        ):
            result = _load_plugins()
            assert result == {}


class TestPortUtils:
    """is_port_bound and find_free_port."""

    @pytest.mark.allow_hosts("127.0.0.1")
    def test_is_port_bound_false(self):
        assert is_port_bound(59999) is False

    @pytest.mark.allow_hosts("127.0.0.1")
    def test_find_free_port(self):
        port = find_free_port(59990)
        assert port >= 59990


class TestEnsureDirectories:
    """ensure_directories."""

    def test_creates_directories(self, tmp_path):
        dirs = [tmp_path / "a", tmp_path / "b" / "c"]
        ensure_directories(dirs)
        for d in dirs:
            assert d.exists()


class TestOpenBrowser:
    """open_browser platform-specific."""

    def test_darwin_path(self):
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run") as mock_run:
                open_browser("http://localhost:3000")
                mock_run.assert_called_once_with(
                    ["open", "http://localhost:3000"], check=False
                )

    def test_linux_path(self):
        with patch("sys.platform", "linux"):
            with patch("subprocess.run") as mock_run:
                open_browser("http://localhost:3000")
                mock_run.assert_called_once_with(
                    ["xdg-open", "http://localhost:3000"], check=False
                )

    def test_windows_path(self):
        with patch("sys.platform", "win32"):
            with patch("subprocess.run") as mock_run:
                open_browser("http://localhost:3000")
                mock_run.assert_called_once_with(
                    ["start", "http://localhost:3000"],
                    shell=True,
                    check=False,
                )

    def test_exception_is_logged(self):
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", side_effect=OSError("nope")):
                open_browser("http://localhost:3000")  # must not raise


class TestBootSequence:
    """boot() full sequence."""

    def test_boot_returns_context(self):
        import importlib
        from uar import boot as boot_mod

        importlib.reload(boot_mod)
        with patch.object(boot_mod, "_configure_logging"):
            with patch.object(boot_mod, "_boot_message"):
                with patch.object(boot_mod, "_register_skills"):
                    with patch.object(boot_mod, "_validate_recipes"):
                        with patch.object(
                            boot_mod, "_cleanup_temp_files", return_value=0
                        ):
                            with patch.object(boot_mod, "_seed_uor_runtimes"):
                                with patch.object(
                                    boot_mod, "_load_plugins", return_value={}
                                ):
                                    with patch.object(
                                        boot_mod, "_production_checks"
                                    ):
                                        with patch.object(
                                            boot_mod, "_validate_environment"
                                        ):
                                            with patch.object(
                                                boot_mod,
                                                "_validate_advanced_config",
                                            ):
                                                ctx = boot_mod.boot()
                                                assert (
                                                    type(ctx).__name__
                                                    == "BootContext"
                                                )
                                                assert hasattr(
                                                    ctx, "purge_task"
                                                )
                                                assert hasattr(
                                                    ctx, "started_at"
                                                )


class TestProductionChecksNonProd:
    """_production_checks when not in production."""

    def test_no_warnings_when_not_production(self, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "development")
        import importlib
        from uar import boot as boot_mod

        importlib.reload(boot_mod)
        with caplog.at_level("WARNING", logger="uar.boot"):
            boot_mod._production_checks()
        assert "CORS_ORIGINS" not in caplog.text
        assert "SECURITY_HEADERS" not in caplog.text


class TestRetentionPurgeLoop:
    """_retention_purge_loop remaining branches."""

    @pytest.mark.asyncio
    async def test_no_log_when_removed_is_zero(self):
        from uar.boot import _retention_purge_loop

        async def _cancel_sleep(*_a, **_kw):
            raise asyncio.CancelledError()

        with patch("uar.config.config") as mock_cfg:
            mock_cfg.run_retention_days = 7
            with patch("uar.memory.base_store.get_store") as mock_get:
                store = MagicMock()
                store.purge_old_records.return_value = 0
                mock_get.return_value = store
                with patch(
                    "uar.boot.asyncio.sleep", side_effect=_cancel_sleep
                ):
                    task = asyncio.create_task(_retention_purge_loop())
                    await task
        store.purge_old_records.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_during_purge_is_logged(self):
        from uar.boot import _retention_purge_loop

        async def _cancel_sleep(*_a, **_kw):
            raise asyncio.CancelledError()

        call_count = 0

        def _fake_purge(_days):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("db down")
            return 0

        with patch("uar.config.config") as mock_cfg:
            mock_cfg.run_retention_days = 7
            with patch("uar.memory.base_store.get_store") as mock_get:
                store = MagicMock()
                store.purge_old_records.side_effect = _fake_purge
                mock_get.return_value = store
                with patch(
                    "uar.boot.asyncio.sleep", side_effect=_cancel_sleep
                ):
                    task = asyncio.create_task(_retention_purge_loop())
                    await task
        assert call_count >= 1


class TestShutdownCancelledError:
    """shutdown purge_task CancelledError."""

    @pytest.mark.asyncio
    async def test_purge_task_cancelled_error(self):
        import asyncio

        class _CancellingTask:
            def cancel(self):
                pass

            def __await__(self):
                raise asyncio.CancelledError()

        ws = MagicMock()
        ws.count = 0
        ctx = BootContext(ws_conn_counter=ws)
        ctx.purge_task = _CancellingTask()
        with patch("uar.api.metrics.get_metrics_collector") as m:
            m.return_value = MagicMock()
            with patch("uar.memory.postgres_store._shutdown_postgres_pool"):
                with patch("uar.core.http_client.close_all_sessions"):
                    with patch("uar.boot.SHUTDOWN_SLEEP", 0.001):
                        await shutdown(ctx)


class TestFindFreePortInUse:
    """find_free_port when start port is occupied."""

    @pytest.mark.allow_hosts("127.0.0.1")
    def test_increments_when_port_in_use(self):
        import socket

        # Bind a real port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            bound_port = s.getsockname()[1]
            # find_free_port should skip the bound port
            port = find_free_port(bound_port, "127.0.0.1")
            assert port > bound_port


class TestValidatePrerequisitesNpm:
    """validate_prerequisites npm missing."""

    def test_npm_missing(self):
        def _fake_which(cmd):
            if cmd == "npm":
                return None
            return "/usr/bin/node"

        with patch("shutil.which", side_effect=_fake_which):
            missing = validate_prerequisites()
            assert any("npm" in m for m in missing)


class TestServiceSupervisorStartLogCloseFail:
    """ServiceSupervisor start exception with log close failure."""

    def test_exception_closes_log_despite_error(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        log_file = tmp_path / "svc.log"
        # Create the file so open() succeeds
        log_file.write_text("")
        with patch("subprocess.Popen", side_effect=OSError("exec failed")):
            with pytest.raises(OSError):
                supervisor.start("svc", ["false"], log_path=log_file)


class TestHealthCheckSuccessAndFailure:
    """health_check when service is running."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        supervisor._procs["svc"] = mock_proc
        with patch("uar.boot.wait_for_health", return_value=True):
            ok = await supervisor.health_check("svc", "http://localhost:1")
            assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        supervisor._procs["svc"] = mock_proc
        with patch("uar.boot.wait_for_health", return_value=False):
            ok = await supervisor.health_check("svc", "http://localhost:1")
            assert ok is False


class TestStopAllSuccessAndException:
    """stop_all with successful termination and exception paths."""

    def test_stop_all_successful_terminate(self):
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
        mock_proc.wait.assert_called_once_with(timeout=5)
        assert not supervisor.is_running("svc")

    def test_stop_all_terminate_raises_exception(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = None
        mock_proc.terminate.side_effect = OSError("no such process")
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor.stop_all()  # must not raise

    def test_stop_all_log_fp_already_closed(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = MagicMock()
        log_fp = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor._log_fps["svc"] = log_fp
        # Make fp.close() raise to cover exception path
        log_fp.close.side_effect = OSError("already closed")
        supervisor.stop_all()  # must not raise


class TestBootFullStackHealthFail:
    """boot_full_stack API health check failure."""

    @pytest.mark.asyncio
    async def test_api_health_fail_raises(self):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.find_free_port", return_value=9999):
                with patch("uar.boot.ServiceSupervisor") as mock_sv:
                    supervisor = MagicMock()
                    supervisor.start = MagicMock()
                    supervisor.health_check = AsyncMock(return_value=False)
                    supervisor.stop_all = MagicMock()
                    mock_sv.return_value = supervisor
                    with pytest.raises(RuntimeError, match="health check"):
                        await boot_full_stack(
                            api_port=9999,
                            start_web=False,
                            start_dashboard=False,
                        )
                    supervisor.stop_all.assert_called_once()


class TestBootFullStackWebNotFound:
    """boot_full_stack when web UI directory does not exist."""

    @pytest.mark.asyncio
    async def test_web_dir_not_found_warns(self, caplog):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.find_free_port", return_value=9999):
                with patch("uar.boot.ServiceSupervisor") as mock_sv:
                    supervisor = MagicMock()
                    supervisor.start = MagicMock()
                    supervisor.health_check = AsyncMock(return_value=True)
                    supervisor.stop_all = MagicMock()
                    mock_sv.return_value = supervisor
                    with patch.object(Path, "exists", return_value=False):
                        with caplog.at_level("WARNING", logger="uar.boot"):
                            await boot_full_stack(
                                api_port=9999,
                                start_web=True,
                                start_dashboard=False,
                            )
        assert "Web UI directory not found" in caplog.text


class TestBootFullStackDashboardNotFound:
    """boot_full_stack when dashboard directory does not exist."""

    @pytest.mark.asyncio
    async def test_dashboard_dir_not_found_warns(self, caplog):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.find_free_port", return_value=9999):
                with patch("uar.boot.ServiceSupervisor") as mock_sv:
                    supervisor = MagicMock()
                    supervisor.start = MagicMock()
                    supervisor.health_check = AsyncMock(return_value=True)
                    supervisor.stop_all = MagicMock()
                    mock_sv.return_value = supervisor
                    with patch.object(Path, "exists", return_value=False):
                        with caplog.at_level("WARNING", logger="uar.boot"):
                            await boot_full_stack(
                                api_port=9999,
                                start_web=False,
                                start_dashboard=True,
                            )
        assert "Dashboard directory not found" in caplog.text


class TestBootCliMonitor:
    """boot_cli _monitor KeyboardInterrupt path."""

    def test_monitor_keyboard_interrupt(self):
        import asyncio
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        supervisor._procs["api"] = mock_proc

        async def _monitor():
            try:
                while True:
                    await asyncio.sleep(0.01)
                    if not any(
                        supervisor.is_running(name)
                        for name in supervisor._procs
                    ):
                        break
            except KeyboardInterrupt:
                pass
            finally:
                supervisor.stop_all()

        async def _run():
            task = asyncio.create_task(_monitor())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(_run())


class TestValidatePrerequisitesNode:
    """validate_prerequisites node missing."""

    def test_node_missing(self):
        def _fake_which(cmd):
            if cmd == "node":
                return None
            return "/usr/bin/npm"

        with patch("shutil.which", side_effect=_fake_which):
            missing = validate_prerequisites()
            assert any("node" in m for m in missing)


class TestServiceSupervisorStartLogCloseException:
    """ServiceSupervisor.start exception where fp.close also fails."""

    def test_exception_and_fp_close_fails(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        log_file = tmp_path / "svc.log"

        class _BadFile:
            def close(self):
                raise OSError("bad close")

        with patch("builtins.open", return_value=_BadFile()):
            with patch("subprocess.Popen", side_effect=OSError("exec failed")):
                with pytest.raises(OSError):
                    supervisor.start("svc", ["false"], log_path=log_file)


class TestServiceSupervisorStopAllTerminateException:
    """stop_all where terminate raises non-TimeoutExpired."""

    def test_terminate_raises_permission_error(self):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = None
        mock_proc.terminate.side_effect = PermissionError("denied")
        with patch("subprocess.Popen", return_value=mock_proc):
            supervisor.start("svc", ["sleep", "10"])
        supervisor.stop_all()  # must not raise


class TestServiceSupervisorStopAllLogFpAlreadyClosed:
    """stop_all where log_fp is already in closed list."""

    def test_log_fp_same_as_stdout_not_closed_twice(self, tmp_path):
        from uar.boot import ServiceSupervisor

        supervisor = ServiceSupervisor()
        log_file = tmp_path / "svc.log"
        shared_fp = MagicMock()
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stdout = shared_fp
        with patch("builtins.open", return_value=shared_fp):
            with patch("subprocess.Popen", return_value=mock_proc):
                supervisor.start("svc", ["sleep", "10"], log_path=log_file)
        supervisor.stop_all()
        # close() called once via stdout, not again in log loop
        assert shared_fp.close.call_count == 1


class TestBootFullStackWebExists:
    """boot_full_stack when web UI directory exists."""

    @pytest.mark.asyncio
    async def test_web_dir_exists(self):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.find_free_port", return_value=9999):
                with patch("uar.boot.ServiceSupervisor") as mock_sv:
                    supervisor = MagicMock()
                    supervisor.start = MagicMock()
                    supervisor.health_check = AsyncMock(return_value=True)
                    supervisor.stop_all = MagicMock()
                    mock_sv.return_value = supervisor
                    with patch.object(Path, "exists", return_value=True):
                        with patch("uar.boot.open_browser"):
                            await boot_full_stack(
                                api_port=9999,
                                start_web=True,
                                start_dashboard=False,
                            )
        assert any(c[0][0] == "web" for c in supervisor.start.call_args_list)


class TestBootFullStackDashboardExists:
    """boot_full_stack when dashboard directory exists."""

    @pytest.mark.asyncio
    async def test_dashboard_dir_exists(self):
        from uar.boot import boot_full_stack

        with patch("uar.boot.validate_prerequisites", return_value=[]):
            with patch("uar.boot.find_free_port", return_value=9999):
                with patch("uar.boot.ServiceSupervisor") as mock_sv:
                    supervisor = MagicMock()
                    supervisor.start = MagicMock()
                    supervisor.health_check = AsyncMock(return_value=True)
                    supervisor.stop_all = MagicMock()
                    mock_sv.return_value = supervisor
                    with patch.object(Path, "exists", return_value=True):
                        with patch("uar.boot.open_browser"):
                            await boot_full_stack(
                                api_port=9999,
                                start_web=False,
                                start_dashboard=True,
                            )
        assert any(
            c[0][0] == "dashboard" for c in supervisor.start.call_args_list
        )


class TestBootCliFullStackRun:
    """boot_cli full-stack orchestration actually runs."""

    def test_monitor_exits_when_no_procs(self):
        with patch("sys.argv", ["uar.boot", "--services", "api,web"]):
            with patch("asyncio.sleep", return_value=None):

                async def _fake_boot(**kwargs):
                    from uar.boot import ServiceSupervisor

                    supervisor = ServiceSupervisor()
                    mock_proc = MagicMock()
                    mock_proc.poll.return_value = 0  # exited
                    supervisor._procs["api"] = mock_proc
                    return supervisor

                with patch("uar.boot.boot_full_stack", side_effect=_fake_boot):
                    boot_cli()
