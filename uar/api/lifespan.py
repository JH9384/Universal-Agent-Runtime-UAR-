"""FastAPI lifespan handler for UAR API startup/shutdown."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


async def _retention_purge_loop() -> None:
    """Background task: purge old run records periodically."""
    from uar.config import config
    from uar.memory.base_store import get_store

    if config.run_retention_days <= 0:
        return

    store = get_store()
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour
            removed = store.purge_old_records(config.run_retention_days)
            if removed > 0:
                logger.info(
                    "Purged %s run records older than %s days",
                    removed,
                    config.run_retention_days,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Retention purge failed: %s", exc)


def create_lifespan(ws_conn_counter):
    """Return an asynccontextmanager lifespan bound to the given
    WebSocket connection counter."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan handler for graceful startup and shutdown."""
        # Startup
        logger.info("UAR API starting up...")
        # Clean up orphaned temp files on startup
        from uar.api.routers.docs import (
            _cleanup_orphaned_temp_files,
            _library_dir,
        )

        library = _library_dir()
        _cleanup_orphaned_temp_files(library)
        # Seed UOR standard runtimes (idempotent)
        try:
            from uar.objects import get_default_store, seed_standard_runtimes

            seed_standard_runtimes(get_default_store())
        except Exception as exc:  # noqa: BLE001 - non-fatal at startup
            logger.warning("UOR runtime seeding skipped: %s", exc)

        # Load external skill plugins (~/.uar/skills/ and PyPI entry points)
        try:
            from uar.skills.plugin import load_plugins

            load_plugins()
        except Exception as exc:  # noqa: BLE001 - non-fatal at startup
            logger.warning("Plugin loading skipped: %s", exc)

        # Production security checks
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

        # Initialize optional OpenTelemetry tracing
        from uar.api.tracing import setup_fastapi_tracing

        setup_fastapi_tracing(app)

        # Validate environment before accepting traffic (fail-fast)
        from uar.config import (
            validate_environment,
            validate_docker_environment,
        )

        env_issues = validate_environment()
        docker_issues = validate_docker_environment()
        all_issues = env_issues + docker_issues
        if all_issues:
            for issue in all_issues:
                logger.error("Startup validation failed: %s", issue)
            raise RuntimeError(
                f"UAR startup validation failed with "
                f"{len(all_issues)} issue(s). Run 'uar doctor' for details."
            )

        # Validate advanced integration configs (non-fatal, logged)
        try:
            from uar.config_advanced import (
                validate_advanced_config,
                log_validation_results,
            )

            adv_results = validate_advanced_config()
            log_validation_results(adv_results)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Advanced config validation skipped: %s", exc)

        # Start background data retention purge task
        purge_task = None
        from uar.config import config

        if config.run_retention_days > 0:
            purge_task = asyncio.create_task(_retention_purge_loop())

        yield
        # Shutdown - drain in-flight requests and WebSocket connections
        if purge_task is not None:
            purge_task.cancel()
            try:
                await purge_task
            except asyncio.CancelledError:
                pass
        logger.info(
            "UAR API shutting down, draining active connections "
            "(%ss grace period)...",
            SHUTDOWN_SLEEP,
        )
        start_shutdown = time.monotonic()
        while time.monotonic() - start_shutdown < SHUTDOWN_SLEEP:
            ws_active = ws_conn_counter.count
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
                "Shutdown grace period expired with %s active "
                "connection(s) remaining",
                ws_conn_counter.count,
            )
        # Shutdown metrics collector flush thread
        try:
            from uar.api.metrics import get_metrics_collector

            get_metrics_collector().shutdown()
        except Exception:
            logger.exception("Metrics collector shutdown failed")
        # Shutdown Postgres connection pool if active
        try:
            from uar.memory.postgres_store import _shutdown_postgres_pool

            _shutdown_postgres_pool()
        except Exception:
            logger.exception("Postgres pool shutdown failed")
        # Close per-domain aiohttp sessions
        try:
            from uar.core.http_client import close_all_sessions

            close_all_sessions()
        except Exception:
            logger.exception("HTTP sessions close failed")
        logger.info("UAR API shutdown complete")

    return lifespan
