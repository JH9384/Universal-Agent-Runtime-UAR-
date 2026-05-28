"""Tests for cache and sandbox router.

Covers router definition and endpoints with mocked auth.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.cache_sandbox import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestRouter:
    """Router configuration."""

    def test_routes_exist(self):
        routes = [r.path for r in router.routes]
        assert "/api/cache/stats" in routes
        assert "/api/cache/invalidate" in routes
        assert "/api/sandbox/health" in routes
        assert "/api/sandbox/eval" in routes


class TestCacheStats:
    """/api/cache/stats endpoint."""

    def _mock_auth(self):
        return patch(
            "uar.api.routers.cache_sandbox._auth_svc.require_user",
            return_value=MagicMock(),
        )

    def test_no_cache(self):
        with self._mock_auth():
            with patch(
                "uar.core.skill_cache.get_skill_cache",
                return_value=None,
            ):
                resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        assert resp.json()["size"] == 0

    def test_with_cache(self):
        cache = MagicMock()
        cache.stats.return_value = {"hits": 10, "misses": 2, "size": 5}
        with self._mock_auth():
            with patch(
                "uar.core.skill_cache.get_skill_cache",
                return_value=cache,
            ):
                resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        assert resp.json()["hits"] == 10


class TestCacheInvalidate:
    """/api/cache/invalidate endpoint."""

    def _mock_auth(self):
        return patch(
            "uar.api.routers.cache_sandbox._auth_svc.require_user",
            return_value=MagicMock(),
        )

    def test_invalidate_all(self):
        cache = MagicMock()
        cache.invalidate.return_value = 5
        with self._mock_auth():
            with patch(
                "uar.core.skill_cache.get_skill_cache",
                return_value=cache,
            ):
                resp = client.post(
                    "/api/cache/invalidate", json={}
                )
        assert resp.status_code == 200
        assert resp.json()["invalidated"] == 5
        assert resp.json()["skill"] is None

    def test_invalidate_skill(self):
        cache = MagicMock()
        cache.invalidate.return_value = 2
        with self._mock_auth():
            with patch(
                "uar.core.skill_cache.get_skill_cache",
                return_value=cache,
            ):
                resp = client.post(
                    "/api/cache/invalidate",
                    json={"skill": "math_compute"},
                )
        assert resp.status_code == 200
        assert resp.json()["invalidated"] == 2
        assert resp.json()["skill"] == "math_compute"


class TestSandboxHealth:
    """/api/sandbox/health endpoint."""

    def _mock_auth(self):
        return patch(
            "uar.api.routers.cache_sandbox._auth_svc.require_user",
            return_value=MagicMock(),
        )

    def test_health(self):
        with self._mock_auth():
            with patch(
                "uar.core.sandbox.WASMSandbox"
            ) as MockSandbox:
                MockSandbox.return_value.health.return_value = {
                    "status": "ok"
                }
                resp = client.get("/api/sandbox/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestSandboxEval:
    """/api/sandbox/eval endpoint."""

    def _mock_auth(self):
        return patch(
            "uar.api.routers.cache_sandbox._auth_svc.require_user",
            return_value=MagicMock(),
        )

    def test_eval_success(self):
        with self._mock_auth():
            with patch(
                "uar.core.sandbox.sandbox_eval",
                return_value=42,
            ):
                resp = client.post(
                    "/api/sandbox/eval",
                    json={"expression": "1 + 1"},
                )
        assert resp.status_code == 200
        assert resp.json()["result"] == 42
        assert resp.json()["status"] == "completed"

    def test_eval_failure(self):
        with self._mock_auth():
            with patch(
                "uar.core.sandbox.sandbox_eval",
                side_effect=Exception("fail"),
            ):
                resp = client.post(
                    "/api/sandbox/eval",
                    json={"expression": "invalid"},
                )
        assert resp.status_code == 400
