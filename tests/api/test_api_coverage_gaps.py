"""Coverage gap tests for API layer modules.

Targets lifespan, middleware, runs router, and streaming router
with mocked dependencies.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


def test_retention_purge_loop_zero_days():
    """When retention_days <= 0, purge loop exits immediately."""
    from uar.api.lifespan import _retention_purge_loop

    with patch("uar.config.config") as mock_cfg:
        mock_cfg.run_retention_days = 0
        asyncio.run(_retention_purge_loop())


@pytest.mark.asyncio
async def test_retention_purge_loop_cancelled():
    """CancelledError must break the loop silently."""
    from uar.api.lifespan import _retention_purge_loop

    with patch("uar.config.config") as mock_cfg:
        mock_cfg.run_retention_days = 1
        with patch("uar.memory.base_store.get_store") as mock_get_store:
            store = MagicMock()
            mock_get_store.return_value = store
            task = asyncio.create_task(_retention_purge_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            # CancelledError is caught inside the loop; task completes
            await task


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TestMiddleware:
    def test_request_body_size_limiter_rejects_large(self):
        """Middleware must reject requests exceeding max body size."""
        from uar.api.middleware import apply_middleware

        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.post("/test")
        async def test_endpoint():
            return {"ok": True}

        big_body = "x" * (11 * 1024 * 1024)  # 11MB
        response = client.post("/test", data=big_body)
        assert response.status_code == 413

    def test_api_version_rewrite(self):
        """/api/v1/ paths must be rewritten to /api/."""
        from uar.api.middleware import apply_middleware

        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        response = client.get("/api/v1/test")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_security_headers(self):
        """Security headers must be present on all responses."""
        from uar.api.middleware import apply_middleware

        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers

    def test_request_logging(self):
        """Request logging middleware must execute without errors."""
        from uar.api.middleware import apply_middleware

        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        response = client.get("/test")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Runs router
# ---------------------------------------------------------------------------


class TestRunsRouter:
    def test_skills_endpoint(self):
        """Skills endpoint must return a list."""
        from uar.api.server import app

        client = TestClient(app)
        response = client.get("/api/uar/skills")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["skills"], list)


# ---------------------------------------------------------------------------
# Streaming router (selected endpoints)
# ---------------------------------------------------------------------------


class TestStreamingRouter:
    def test_stream_goal_ws_rejects_without_upgrade(self):
        """WebSocket endpoint without upgrade header must fail."""
        from uar.api.routers.streaming import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Plain HTTP to WebSocket endpoint should fail
        response = client.get("/api/uar/stream/ws")
        assert response.status_code in (403, 404, 426)
