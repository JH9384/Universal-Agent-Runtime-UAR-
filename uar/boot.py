"""UAR unified boot module.

Consolidates startup/shutdown logic previously scattered across
``lifespan.py``, ``server.py``, and shell scripts into a single
importable module.

Usage::

    from uar.boot import create_app, BootContext

    ctx = BootContext()
    app = create_app(ctx)

Or from the command line::

    python -m uar.boot --port 8000
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SHUTDOWN_SLEEP = max(
    0.0,
    float(os.getenv("SHUTDOWN_GRACE_SECONDS", "30").strip() or "30"),
)

_is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
_default_cors = "" if _is_production else "http://localhost:3000"
CORS_ORIGINS = [
    o for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o
]


def _configure_logging() -> None:
    """Set up root logging for the boot process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _boot_message() -> None:
    """Emit the canonical boot log line."""
    from uar.version import get_uar_version
    from uar.compat.uor_version import get_uor_version

    logger.info(
        "Booting UAR %s (aligned with UOR %s)",
        get_uar_version(),
        get_uor_version(),
    )


def _register_skills() -> None:
    """Import the skill package so all @register_skill decorators fire."""
    import uar.skills  # noqa: F401


def _validate_recipes() -> None:
    """Validate that every recipe references registered skills."""
    from uar.core.recipes import validate_recipes

    validate_recipes()


def _cleanup_temp_files() -> int:
    """Remove orphaned .tmp files from the library directory.

    Returns the number of files cleaned up.
    """
    from uar.api.routers.docs import _cleanup_orphaned_temp_files, _library_dir

    library = _library_dir()
    return _cleanup_orphaned_temp_files(library)


def _seed_uor_runtimes() -> None:
    """Seed UOR standard runtimes (idempotent, non-fatal)."""
    try:
        from uar.objects import get_default_store, seed_standard_runtimes

        seed_standard_runtimes(get_default_store())
    except Exception as exc:
        logger.warning("UOR runtime seeding skipped: %s", exc)


def _load_plugins() -> Dict[str, int]:
    """Load external skill plugins (non-fatal).

    Returns a mapping of source name → number of skills registered.
    """
    try:
        from uar.skills.plugin import load_plugins

        return load_plugins()
    except Exception as exc:
        logger.warning("Plugin loading skipped: %s", exc)
        return {}


def _validate_environment() -> None:
    """Fail-fast if the environment is mis-configured."""
    from uar.config import validate_environment, validate_docker_environment

    env_issues = validate_environment()
    docker_issues = validate_docker_environment()
    all_issues = env_issues + docker_issues
    if all_issues:
        for issue in all_issues:
            logger.error("Startup validation failed: %s", issue)
        raise RuntimeError(
            f"UAR startup validation failed with {len(all_issues)} issue(s). "
            "Run 'uar doctor' for details."
        )


def _validate_advanced_config() -> None:
    """Validate advanced integration configs (non-fatal)."""
    try:
        from uar.config_advanced import (
            validate_advanced_config,
            log_validation_results,
        )

        results = validate_advanced_config()
        log_validation_results(results)
    except Exception as exc:
        logger.warning("Advanced config validation skipped: %s", exc)


def _production_checks() -> None:
    """Log warnings for missing production security settings."""
    if _is_production:
        if not CORS_ORIGINS or CORS_ORIGINS == [""]:
            logger.warning(
                "CORS_ORIGINS is not configured in production. "
                "All cross-origin requests will be blocked."
            )
        sec_headers = os.getenv("SECURITY_HEADERS", "").lower()
        if sec_headers != "enabled":
            logger.warning(
                "SECURITY_HEADERS not enabled in production. "
                "Consider setting SECURITY_HEADERS=enabled."
            )


# ---------------------------------------------------------------------------
# Background task: periodic retention purge
# ---------------------------------------------------------------------------

async def _retention_purge_loop() -> None:
    """Background task: purge old run records periodically."""
    from uar.config import config
    from uar.memory.base_store import get_store

    if config.run_retention_days <= 0:
        return

    store = get_store()
    while True:
        try:
            await asyncio.sleep(3600)
            removed = store.purge_old_records(config.run_retention_days)
            if removed > 0:
                logger.info(
                    "Purged %s run records older than %s days",
                    removed,
                    config.run_retention_days,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Retention purge failed: %s", exc)


# ---------------------------------------------------------------------------
# Boot context
# ---------------------------------------------------------------------------

@dataclass
class BootContext:
    """Mutable bag of state created during boot and torn down on shutdown."""

    ws_conn_counter: Any = field(default_factory=lambda: None, repr=False)
    purge_task: Optional[asyncio.Task] = None
    started_at: float = field(default_factory=time.time)
    plugins_loaded: Dict[str, int] = field(default_factory=dict)
    temp_files_cleaned: int = 0

    def __post_init__(self) -> None:
        if self.ws_conn_counter is None:
            from uar.api.state import _ws_conn_counter

            self.ws_conn_counter = _ws_conn_counter


# ---------------------------------------------------------------------------
# Core boot sequence
# ---------------------------------------------------------------------------

def boot() -> BootContext:
    """Run the synchronous portion of the boot sequence.

    Returns a :class:`BootContext` carrying mutable state that must
    be passed to :func:`shutdown` (or the FastAPI lifespan) later.
    """
    _configure_logging()
    _boot_message()

    ctx = BootContext()

    # 1. Register skills
    _register_skills()

    # 2. Validate recipes (must happen after skills are loaded)
    _validate_recipes()

    # 3. Clean up orphaned temp files
    ctx.temp_files_cleaned = _cleanup_temp_files()

    # 4. Seed UOR runtimes
    _seed_uor_runtimes()

    # 5. Load external plugins
    ctx.plugins_loaded = _load_plugins()

    # 6. Production security checks
    _production_checks()

    # 7. Validate environment (fail-fast)
    _validate_environment()

    # 8. Validate advanced configs
    _validate_advanced_config()

    logger.info("Boot sequence complete")
    return ctx


async def shutdown(ctx: BootContext) -> None:
    """Graceful shutdown sequence.

    Cancels background tasks, drains connections, and flushes metrics.
    """
    if ctx.purge_task is not None:
        ctx.purge_task.cancel()
        try:
            await ctx.purge_task
        except asyncio.CancelledError:
            pass

    logger.info(
        "UAR API shutting down, draining active connections "
        "(%ss grace period)...",
        SHUTDOWN_SLEEP,
    )
    start_shutdown = time.monotonic()
    while time.monotonic() - start_shutdown < SHUTDOWN_SLEEP:
        ws_active = ctx.ws_conn_counter.count
        if ws_active == 0:
            logger.info("All connections drained cleanly")
            break
        logger.info(
            "Waiting for %s active WebSocket(s) to close...",
            ws_active,
        )
        await asyncio.sleep(1.0)
    else:
        logger.warning(
            (
                "Shutdown grace period expired with %s active "
                "connection(s) remaining"
            ),
            ctx.ws_conn_counter.count,
        )

    # Metrics collector
    try:
        from uar.api.metrics import get_metrics_collector

        get_metrics_collector().shutdown()
    except Exception:
        logger.exception("Metrics collector shutdown failed")

    # Postgres pool
    try:
        from uar.memory.postgres_store import _shutdown_postgres_pool

        _shutdown_postgres_pool()
    except Exception:
        logger.exception("Postgres pool shutdown failed")

    # HTTP sessions
    try:
        from uar.core.http_client import close_all_sessions

        close_all_sessions()
    except Exception:
        logger.exception("HTTP sessions close failed")

    logger.info("UAR API shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

def create_lifespan(ctx: BootContext):
    """Return an ``@asynccontextmanager`` lifespan for FastAPI."""

    @asynccontextmanager
    async def lifespan(app: Any):
        # Startup — background tasks that need the event loop
        from uar.api.tracing import setup_fastapi_tracing
        from uar.config import config

        setup_fastapi_tracing(app)

        if config.run_retention_days > 0:
            ctx.purge_task = asyncio.create_task(_retention_purge_loop())

        yield

        # Shutdown
        await shutdown(ctx)

    return lifespan


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def create_app(ctx: Optional[BootContext] = None) -> Any:
    """Create and return the fully configured FastAPI application.

    This performs the full boot sequence (unless *ctx* is supplied) and
    wires all routers, middleware, and exception handlers.
    """
    from fastapi import FastAPI, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    from uar.api.middleware import (
        apply_middleware,
        require_auth,
        register_metrics_middleware,
    )
    from uar.api.exception_handlers import register_exception_handlers
    from uar.version import get_uar_version

    if ctx is None:
        ctx = boot()

    app = FastAPI(
        title="UAR API",
        description=(
            "Universal Agent Runtime API with production security features"
        ),
        version=get_uar_version(),
        lifespan=create_lifespan(ctx),
    )

    # CORS
    CORS_ALLOW_CREDENTIALS = (
        os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    )
    CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "*")
    CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=(
            [CORS_ALLOW_METHODS] if CORS_ALLOW_METHODS != "*" else ["*"]
        ),
        allow_headers=(
            [CORS_ALLOW_HEADERS] if CORS_ALLOW_HEADERS != "*" else ["*"]
        ),
    )

    # Trusted Host
    _trusted_hosts_env = os.getenv("TRUSTED_HOSTS", "").strip()
    if _trusted_hosts_env:
        _hosts = [
            h.strip() for h in _trusted_hosts_env.split(",") if h.strip()
        ]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

    # Request logging, body parsing, size limits
    apply_middleware(app)

    # Gzip
    app.add_middleware(
        GZipMiddleware,
        minimum_size=max(
            0, int(os.getenv("UAR_GZIP_MIN_SIZE", "1024").strip() or "1024")
        ),
    )

    # Metrics
    register_metrics_middleware(app)

    # Routers
    from uar.api.advanced_endpoints import router as advanced_router
    from uar.api.routers.health import router as health_router
    from uar.api.routers.recipes import router as recipes_router
    from uar.api.routers.cache_sandbox import router as cache_sandbox_router
    from uar.api.routers.metrics import router as metrics_router
    from uar.api.routers.docs import router as docs_router
    from uar.api.routers.runs import router as runs_router
    from uar.api.routers.streaming import router as streaming_router
    from uar.api.routers import uor_router

    app.include_router(advanced_router, dependencies=[Depends(require_auth)])
    app.include_router(health_router)
    app.include_router(recipes_router)
    app.include_router(
        cache_sandbox_router, dependencies=[Depends(require_auth)]
    )
    app.include_router(metrics_router)
    app.include_router(docs_router)
    app.include_router(runs_router)
    app.include_router(streaming_router)
    app.include_router(uor_router, dependencies=[Depends(require_auth)])

    register_exception_handlers(app)
    return app


# ---------------------------------------------------------------------------
# System-level orchestration (previously in shell scripts only)
# ---------------------------------------------------------------------------


def is_port_bound(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if *host:port* is already listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_free_port(start: int = 8000, host: str = "127.0.0.1") -> int:
    """Return the first free port at or after *start*."""
    port = start
    while is_port_bound(port, host):
        logger.info("Port %s in use, trying %s", port, port + 1)
        port += 1
    return port


async def wait_for_health(
    url: str,
    *,
    attempts: int = 40,
    interval: float = 0.25,
    timeout: float = 10.0,
) -> bool:
    """Poll *url* until it returns 200 or limits are exhausted.

    Returns True if healthy, False otherwise.
    """
    import urllib.request

    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(interval)
    return False


def validate_prerequisites() -> List[str]:
    """Check that node, npm, and a suitable Python are available.

    Returns a list of missing prerequisite descriptions.
    """
    missing: List[str] = []

    if sys.version_info < (3, 10):
        missing.append(
            f"Python 3.10+ required (found {sys.version_info.major}."
            f"{sys.version_info.minor})"
        )

    if shutil.which("node") is None:
        missing.append("node not found (install from nodejs.org)")
    if shutil.which("npm") is None:
        missing.append("npm not found")

    return missing


def ensure_directories(paths: List[Path]) -> None:
    """Create directories if they do not already exist."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", p)


def open_browser(url: str) -> None:
    """Open *url* in the default browser (macOS / Linux / Windows)."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", url], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", url], check=False)
        elif sys.platform == "win32":
            subprocess.run(["start", url], shell=True, check=False)
    except Exception as exc:
        logger.warning("Could not open browser: %s", exc)


# ---------------------------------------------------------------------------
# Service supervisor
# ---------------------------------------------------------------------------

class ServiceSupervisor:
    """Start, monitor, and stop external service processes.

    Replaces the PID-tracking logic in ``boot.sh``.
    """

    def __init__(self) -> None:
        self._procs: Dict[str, subprocess.Popen] = {}

    def start(
        self,
        name: str,
        cmd: List[str],
        *,
        cwd: Optional[Path] = None,
        log_path: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> int:
        """Start a named service and return its PID."""
        if name in self._procs:
            raise RuntimeError(f"Service '{name}' already running")

        kwargs: Dict[str, Any] = {}
        if cwd is not None:
            kwargs["cwd"] = str(cwd)
        if env is not None:
            kwargs["env"] = {**os.environ, **env}
        if log_path is not None:
            fp = open(log_path, "a")
            kwargs["stdout"] = fp
            kwargs["stderr"] = subprocess.STDOUT

        proc = subprocess.Popen(cmd, **kwargs)
        self._procs[name] = proc
        logger.info("Started %s (pid=%s)", name, proc.pid)
        return proc.pid

    def is_running(self, name: str) -> bool:
        """Return True if the named service is still alive."""
        proc = self._procs.get(name)
        if proc is None:
            return False
        return proc.poll() is None

    async def health_check(
        self, name: str, url: str, **poll_kwargs: Any
    ) -> bool:
        """Poll a service's health endpoint.

        Logs a warning and returns False on failure.
        """
        if not self.is_running(name):
            logger.error("Service '%s' exited before health check", name)
            return False

        ok = await wait_for_health(url, **poll_kwargs)
        if ok:
            logger.info("Health check passed for %s", name)
        else:
            logger.error("Health check timed out for %s", name)
        return ok

    def stop_all(self) -> None:
        """Send SIGTERM to all tracked processes and wait for exit."""
        logger.info("Stopping all supervised services...")
        for name, proc in list(self._procs.items()):
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception as exc:
                    logger.warning("Error stopping %s: %s", name, exc)
            if hasattr(proc, "stdout") and proc.stdout:
                proc.stdout.close()
            logger.info("Stopped %s", name)
        self._procs.clear()


# ---------------------------------------------------------------------------
# Full-stack boot orchestrator
# ---------------------------------------------------------------------------

async def boot_full_stack(
    *,
    api_port: int = 8000,
    web_port: int = 5173,
    dashboard_port: int = 3001,
    host: str = "127.0.0.1",
    open_browser_ui: bool = True,
    start_web: bool = True,
    start_dashboard: bool = True,
) -> ServiceSupervisor:
    """Boot API + optional Web + optional Dashboard with health checks.

    This is the Python equivalent of ``./boot.sh``.
    """
    _configure_logging()
    _boot_message()

    # Prerequisites
    missing = validate_prerequisites()
    if missing:
        for m in missing:
            logger.error("Prerequisite missing: %s", m)
        raise RuntimeError(
            f"Boot aborted: {len(missing)} prerequisite(s) missing"
        )

    # Resolve free ports
    api_port = find_free_port(api_port, host)
    if start_web:
        web_port = find_free_port(web_port, host)
    if start_dashboard:
        dashboard_port = find_free_port(dashboard_port, host)

    api_url = f"http://{host}:{api_port}"
    web_url = f"http://{host}:{web_port}" if start_web else None
    dashboard_url = (
        f"http://{host}:{dashboard_port}" if start_dashboard else None
    )

    logger.info(
        "Ports: API=%s Web=%s Dashboard=%s",
        api_port,
        web_port if start_web else "(skipped)",
        dashboard_port if start_dashboard else "(skipped)",
    )

    # Boot context + FastAPI app (context is created inside create_app)
    _ = boot()  # noqa: F841 — side-effect only (skills, validation)

    # Determine Python executable
    python_exe = sys.executable

    supervisor = ServiceSupervisor()

    try:
        # Start API
        api_log = Path("/tmp") / "uar_api.log"
        supervisor.start(
            "api",
            [
                python_exe,
                "-m",
                "uvicorn",
                "uar.api.server:app",
                "--host",
                host,
                "--port",
                str(api_port),
            ],
            log_path=api_log,
        )

        ok = await supervisor.health_check(
            "api", f"{api_url}/api/health", attempts=40, interval=0.25
        )
        if not ok:
            raise RuntimeError("API health check failed")

        # Start Web UI
        if start_web:
            web_dir = Path(__file__).parent.parent / "apps" / "web"
            if web_dir.exists():
                web_log = Path("/tmp") / "uar_web.log"
                supervisor.start(
                    "web",
                    [
                        "npm",
                        "run",
                        "dev",
                        "--",
                        "--port",
                        str(web_port),
                        "--host",
                        host,
                    ],
                    cwd=web_dir,
                    log_path=web_log,
                )
                await supervisor.health_check(
                    "web", web_url, attempts=40, interval=0.5
                )
                if open_browser_ui:
                    open_browser(web_url)
            else:
                logger.warning("Web UI directory not found: %s", web_dir)

        # Start Dashboard
        if start_dashboard:
            dash_dir = (
                Path(__file__).parent.parent
                / "apps"
                / "operator-dashboard"
            )
            if dash_dir.exists():
                dash_log = Path("/tmp") / "uar_dashboard.log"
                supervisor.start(
                    "dashboard",
                    ["npm", "run", "dev"],
                    cwd=dash_dir,
                    log_path=dash_log,
                )
                await supervisor.health_check(
                    "dashboard",
                    dashboard_url,
                    attempts=40,
                    interval=0.5,
                )
                if open_browser_ui:
                    open_browser(dashboard_url)
            else:
                logger.warning(
                    "Dashboard directory not found: %s", dash_dir
                )

    except Exception:
        supervisor.stop_all()
        raise

    logger.info(
        "UAR is running\n"
        "  API:       %s\n"
        "  Web UI:    %s\n"
        "  Dashboard: %s\n"
        "  Health:    %s/api/health\n"
        "  Logs:      tail -f /tmp/uar_*.log",
        api_url,
        web_url or "(skipped)",
        dashboard_url or "(skipped)",
        api_url,
    )

    return supervisor


# ---------------------------------------------------------------------------
# CLI entry point (replaces boot.sh / start.sh)
# ---------------------------------------------------------------------------

def boot_cli() -> None:
    """Command-line entry point: ``python -m uar.boot``."""
    parser = argparse.ArgumentParser(
        description="Boot the UAR API server (or full stack)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="API port"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload"
    )
    parser.add_argument("--env-file", help="Path to .env file")
    parser.add_argument(
        "--services",
        default="api",
        help="Comma-separated: api,web,dashboard",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Skip browser auto-open",
    )
    args = parser.parse_args()

    if args.env_file and os.path.isfile(args.env_file):
        import dotenv

        dotenv.load_dotenv(args.env_file)
        logger.info("Loaded environment from %s", args.env_file)

    services = {s.strip() for s in args.services.split(",")}
    start_web = "web" in services
    start_dashboard = "dashboard" in services

    if start_web or start_dashboard:
        # Full-stack orchestration
        async def _monitor(supervisor: ServiceSupervisor) -> None:
            """Wait for any supervised service to exit."""
            try:
                while True:
                    await asyncio.sleep(1)
                    if not any(
                        supervisor.is_running(name)
                        for name in supervisor._procs
                    ):
                        break
            except KeyboardInterrupt:
                pass
            finally:
                supervisor.stop_all()

        supervisor = asyncio.run(
            boot_full_stack(
                api_port=args.port,
                host=args.host,
                open_browser_ui=not args.no_browser,
                start_web=start_web,
                start_dashboard=start_dashboard,
            )
        )
        asyncio.run(_monitor(supervisor))
    else:
        # API-only (simple path)
        import uvicorn

        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
        )


if __name__ == "__main__":
    boot_cli()
