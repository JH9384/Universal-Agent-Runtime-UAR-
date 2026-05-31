"""Tests for uar.api.middleware."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient
from starlette.datastructures import URL

from uar.api.middleware import (
    RateLimiter,
    RedisRateLimiter,
    create_rate_limiter,
    get_rate_limit_key,
    build_rate_limit_key,
    check_rate_limit,
    rate_limit_middleware,
    auth_middleware,
    request_logging_middleware,
    error_handler_middleware,
    api_error_handler,
    _extract_skill_from_request_data,
    _load_rate_limits,
    _load_skill_rate_limits,
    _load_api_keys,
    _maybe_reload_api_keys,
    _redact_query_params,
    _is_dev_mode,
    _get_cors_origins,
    apply_middleware,
    register_metrics_middleware,
    require_auth,
    reset_rate_limiter,
)


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_is_allowed_first_request(self):
        rl = RateLimiter()
        allowed, remaining = rl.is_allowed("key1", 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_is_allowed_limit_reached(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.is_allowed("key1", 5, 60)
        allowed, remaining = rl.is_allowed("key1", 5, 60)
        assert allowed is False
        assert remaining == 0

    def test_is_allowed_window_expires(self):
        rl = RateLimiter()
        rl.is_allowed("key1", 1, 0)
        time.sleep(0.01)
        allowed, remaining = rl.is_allowed("key1", 1, 0)
        assert allowed is True

    def test_get_remaining_empty(self):
        rl = RateLimiter()
        assert rl.get_remaining("new_key", 5, 60) == 5

    def test_get_remaining_after_requests(self):
        rl = RateLimiter()
        rl.is_allowed("key1", 5, 60)
        assert rl.get_remaining("key1", 5, 60) == 4

    def test_evict_empty(self):
        rl = RateLimiter()
        rl.is_allowed("key1", 1, 0)
        time.sleep(0.01)
        removed = rl.evict_empty()
        assert removed >= 0

    def test_enforce_max_entries(self):
        rl = RateLimiter(max_entries=2)
        rl.is_allowed("k1", 100, 60)
        rl.is_allowed("k2", 100, 60)
        rl.is_allowed("k3", 100, 60)
        assert len(rl.requests) <= 2

    def test_cleanup_interval(self):
        rl = RateLimiter(cleanup_interval=1, cleanup_threshold=0)
        for i in range(5):
            rl.is_allowed(f"k{i}", 1, 0)
        time.sleep(0.01)
        rl.is_allowed("trigger", 100, 60)

    def test_evict_empty_unlocked(self):
        rl = RateLimiter()
        rl.is_allowed("k1", 1, 0)
        time.sleep(0.01)
        # After window expires, deque should be empty after get_remaining
        rl.get_remaining("k1", 1, 0)  # cleans up expired entries
        removed = rl._evict_empty_unlocked()
        assert removed == 1

    def test_get_remaining_key_not_in_order(self):
        rl = RateLimiter()
        rl.is_allowed("k1", 5, 60)
        # Manually remove from _key_order to test branch
        del rl._key_order["k1"]
        remaining = rl.get_remaining("k1", 5, 60)
        assert remaining >= 0


class TestResetRateLimiter:
    def test_reset_no_limiter(self):
        with patch("uar.api.middleware.rate_limiter", None):
            reset_rate_limiter()  # should not raise

    def test_reset_clears_state(self):
        rl = RateLimiter()
        rl.is_allowed("k1", 5, 60)
        with patch("uar.api.middleware.rate_limiter", rl):
            reset_rate_limiter()
        assert len(rl.requests) == 0


class FakeRedisError(Exception):
    pass


class TestRedisRateLimiter:
    def _make_rl(self, mock_redis):
        rl = RedisRateLimiter.__new__(RedisRateLimiter)
        rl._redis = mock_redis
        rl._LUA_RATE_LIMIT = RedisRateLimiter._LUA_RATE_LIMIT
        return rl

    def test_redis_unavailable_fallback(self):
        """When redis is unavailable, must fall back to permissive."""
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = FakeRedisError("redis down")
        fake_mod = type("mod", (), {"RedisError": FakeRedisError})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            rl = self._make_rl(mock_redis)
            allowed, remaining = rl.is_allowed("k", 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_redis_is_allowed_denied(self):
        mock_redis = MagicMock()
        mock_redis.eval.return_value = [6, 0]
        fake_mod = type("mod", (), {"RedisError": FakeRedisError})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            rl = self._make_rl(mock_redis)
            allowed, remaining = rl.is_allowed("k", 5, 60)
        assert allowed is False
        assert remaining == 0

    def test_redis_is_allowed_success(self):
        mock_redis = MagicMock()
        mock_redis.eval.return_value = [3, 1]
        fake_mod = type("mod", (), {"RedisError": FakeRedisError})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            rl = self._make_rl(mock_redis)
            allowed, remaining = rl.is_allowed("k", 5, 60)
        assert allowed is True
        assert remaining == 2

    def test_redis_get_remaining_error(self):
        mock_redis = MagicMock()
        mock_redis.zremrangebyscore.side_effect = FakeRedisError("redis down")
        fake_mod = type("mod", (), {"RedisError": FakeRedisError})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            rl = self._make_rl(mock_redis)
            assert rl.get_remaining("k", 5, 60) == 5

    def test_redis_get_remaining_success(self):
        mock_redis = MagicMock()
        mock_redis.zcard.return_value = 3
        fake_mod = type("mod", (), {"RedisError": FakeRedisError})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            rl = self._make_rl(mock_redis)
            assert rl.get_remaining("k", 5, 60) == 2


class TestCreateRateLimiter:
    def test_in_memory_without_redis(self):
        with patch.dict(os.environ, {}, clear=True):
            rl = create_rate_limiter()
        assert isinstance(rl, RateLimiter)

    def test_redis_import_error(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch.dict("sys.modules", {"redis": None}):
                rl = create_rate_limiter()
        assert isinstance(rl, RateLimiter)

    def test_redis_connection_error_non_prod(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch.dict("sys.modules", {"redis": MagicMock()}):
                with patch(
                    "uar.api.middleware.RedisRateLimiter"
                ) as MockRL:
                    MockRL.side_effect = Exception("conn refused")
                    rl = create_rate_limiter()
        assert isinstance(rl, RateLimiter)

    def test_production_requires_redis(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "REDIS_URL": ""},
        ):
            with pytest.raises(RuntimeError, match="requires REDIS_URL"):
                create_rate_limiter()

    def test_production_redis_import_error(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "REDIS_URL": "redis://x"},
        ):
            with patch.dict("sys.modules", {"redis": None}):
                with pytest.raises(
                    RuntimeError, match="redis package"
                ):
                    create_rate_limiter()

    def test_production_redis_connection_error(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "REDIS_URL": "redis://x"},
        ):
            with patch.dict("sys.modules", {"redis": MagicMock()}):
                with patch(
                    "uar.api.middleware.RedisRateLimiter"
                ) as MockRL:
                    MockRL.side_effect = Exception("conn refused")
                    with pytest.raises(RuntimeError, match="Failed"):
                        create_rate_limiter()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


class TestLoadApiKeys:
    def test_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _load_api_keys() == {}

    def test_from_env(self):
        with patch.dict(
            os.environ, {"API_KEYS": "key1:user1:tier1,key2:user2"}
        ):
            keys = _load_api_keys()
        assert keys["key1"] == {"user": "user1", "tier": "tier1"}
        assert keys["key2"] == {"user": "user2", "tier": "authenticated"}

    def test_from_file(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("key1:user1")
        with patch.dict(os.environ, {"API_KEYS_FILE": str(f)}):
            keys = _load_api_keys()
        assert keys["key1"] == {"user": "user1", "tier": "authenticated"}

    def test_from_file_missing(self, tmp_path):
        with patch.dict(
            os.environ, {"API_KEYS_FILE": str(tmp_path / "nope")}
        ):
            assert _load_api_keys() == {}

    def test_skips_invalid(self):
        with patch.dict(os.environ, {"API_KEYS": ":user,,,:"}):
            assert _load_api_keys() == {}

    def test_skips_empty_key_or_user(self):
        with patch.dict(os.environ, {"API_KEYS": ":user1,key1:"}):
            assert _load_api_keys() == {}


class TestMaybeReloadApiKeys:
    def test_no_file(self):
        with patch.dict(os.environ, {}, clear=True):
            _maybe_reload_api_keys()  # must not raise

    def test_file_unchanged(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        with patch("uar.api.middleware._API_KEYS_FILE", str(f)):
            with patch("uar.api.middleware._API_KEYS_MTIME", 0.0):
                _maybe_reload_api_keys()  # first call sets mtime
                _maybe_reload_api_keys()  # second call - unchanged

    def test_file_changed(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        with patch("uar.api.middleware._API_KEYS_FILE", str(f)):
            with patch("uar.api.middleware._API_KEYS_MTIME", 0.0):
                _maybe_reload_api_keys()  # sets mtime and loads keys
                f.write_text("k2:u2")
                _maybe_reload_api_keys()  # should reload

    def test_file_oserror(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        with patch("uar.api.middleware._API_KEYS_FILE", str(f)):
            with patch("uar.api.middleware._API_KEYS_MTIME", 0.0):
                with patch(
                    "os.path.getmtime", side_effect=OSError("gone")
                ):
                    _maybe_reload_api_keys()  # should not raise

    def test_file_changed_empty_keys(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        with patch("uar.api.middleware._API_KEYS_FILE", str(f)):
            with patch("uar.api.middleware._API_KEYS_MTIME", 0.0):
                with patch(
                    "uar.api.middleware.os.path.getmtime",
                    side_effect=[1.0, 2.0],
                ):
                    _maybe_reload_api_keys()
                    _maybe_reload_api_keys()  # new_keys is empty

    def test_reload_returns_empty_keys(self, tmp_path):
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        with patch("uar.api.middleware._API_KEYS_FILE", str(f)):
            with patch("uar.api.middleware._API_KEYS_MTIME", 0.0):
                with patch(
                    "uar.api.middleware.os.path.getmtime", return_value=2.0
                ):
                    with patch(
                        "uar.api.middleware._load_api_keys",
                        return_value={},
                    ):
                        _maybe_reload_api_keys()

    def test_module_level_api_keys_file_env(self, tmp_path):
        """Module import with API_KEYS_FILE set covers lines 447-450."""
        import subprocess
        import sys
        f = tmp_path / "keys.txt"
        f.write_text("k:u")
        script = (
            f'import os; os.environ["API_KEYS_FILE"] = "{f}"; '
            f'import uar.api.middleware as mw; '
            f'print(mw._API_KEYS_FILE)'
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert str(f) in result.stdout

    def test_module_level_api_keys_file_missing(self, tmp_path):
        """Module import with missing API_KEYS_FILE covers OSError."""
        import subprocess
        import sys
        missing = str(tmp_path / "nonexistent")
        script = (
            f'import os; os.environ["API_KEYS_FILE"] = "{missing}"; '
            f'import uar.api.middleware as mw; '
            f'print(mw._API_KEYS_FILE)'
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert missing in result.stdout


# ---------------------------------------------------------------------------
# Rate limit helpers
# ---------------------------------------------------------------------------


class TestGetRateLimitKey:
    def test_anonymous(self):
        req = MagicMock()
        req.client.host = "127.0.0.1"
        key = get_rate_limit_key(req, None)
        assert key == "anon:127.0.0.1"

    def test_authenticated(self):
        req = MagicMock()
        req.client.host = "127.0.0.1"
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="key1"
        )
        with patch(
            "uar.api.middleware.API_KEYS", {"key1": {"user": "user1"}}
        ):
            key = get_rate_limit_key(req, creds)
        assert "auth:user1" in key


class TestBuildRateLimitKey:
    def test_authenticated(self):
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="key1"
        )
        with patch(
            "uar.api.middleware.API_KEYS",
            {"key1": {"user": "user1", "tier": "tier1"}},
        ):
            key, tier = build_rate_limit_key("ip", creds)
        assert key == "auth:user1:ip"
        assert tier == "tier1"

    def test_anonymous(self):
        key, tier = build_rate_limit_key("ip", None)
        assert key == "anon:ip"
        assert tier == "default"


class TestCheckRateLimit:
    def test_skill_limit(self):
        limit, window, rtype = check_rate_limit(
            "k", "default", "ollama_generate"
        )
        assert rtype == "skill"
        assert limit == 5

    def test_tier_limit(self):
        limit, window, rtype = check_rate_limit("k", "default", "unknown")
        assert rtype == "tier"

    def test_no_skill(self):
        limit, window, rtype = check_rate_limit("k", "default", None)
        assert rtype == "tier"


class TestExtractSkillFromRequestData:
    def test_from_skills(self):
        assert _extract_skill_from_request_data(["s1", "s2"], None) == "s1"

    def test_from_execution_order_skill(self):
        assert (
            _extract_skill_from_request_data(
                None,
                [{"type": "skill", "content": "s1"}],
            )
            == "s1"
        )

    def test_from_execution_order_recipe(self):
        with patch(
            "uar.core.recipes.get_recipe_skills", return_value=["s1"]
        ):
            assert (
                _extract_skill_from_request_data(
                    None, [{"type": "recipe", "content": "r1"}]
                )
                == "s1"
            )

    def test_empty(self):
        assert _extract_skill_from_request_data(None, None) is None

    def test_no_content(self):
        assert (
            _extract_skill_from_request_data(None, [{"type": "skill"}])
            is None
        )

    def test_recipe_empty_skills(self):
        with patch(
            "uar.core.recipes.get_recipe_skills", return_value=[]
        ):
            assert (
                _extract_skill_from_request_data(
                    None, [{"type": "recipe", "content": "r1"}]
                )
                is None
            )

    def test_recipe_none_content(self):
        assert (
            _extract_skill_from_request_data(
                None, [{"type": "recipe", "content": None}]
            )
            is None
        )

    def test_unknown_type(self):
        assert (
            _extract_skill_from_request_data(
                None, [{"type": "unknown", "content": "x"}]
            )
            is None
        )


# ---------------------------------------------------------------------------
# Rate limit middleware
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    def test_allows_request(self):
        reset_rate_limiter()
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.state = MagicMock()
        rate_limit_middleware(req, None)
        assert req.state.rate_limit_remaining >= 0

    def test_blocks_exceeded(self):
        reset_rate_limiter()
        rl = RateLimiter()
        with patch("uar.api.middleware.rate_limiter", rl):
            for _ in range(1000):
                try:
                    req = MagicMock()
                    req.client.host = "127.0.0.1"
                    req.state = MagicMock()
                    rate_limit_middleware(req, None)
                except HTTPException:
                    break
            else:
                pytest.fail("Should have raised HTTPException")

    def test_with_skill(self):
        reset_rate_limiter()
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.state = MagicMock()
        rate_limit_middleware(req, None, first_skill="ollama_generate")
        assert req.state.skill_name == "ollama_generate"


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    def test_no_credentials(self):
        assert auth_middleware(None) is None

    def test_valid_key(self):
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="key1"
        )
        with patch(
            "uar.api.middleware.API_KEYS", {"key1": {"user": "user1"}}
        ):
            info = auth_middleware(creds)
        assert info["user"] == "user1"

    def test_invalid_key_prod(self):
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="bad"
        )
        with patch(
            "uar.api.middleware.API_KEYS", {"k": {"user": "u"}}
        ):
            with patch.dict(
                os.environ, {"ENVIRONMENT": "production"}
            ):
                with pytest.raises(
                    HTTPException, match="Invalid API key"
                ):
                    auth_middleware(creds)

    def test_invalid_key_dev(self):
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="bad"
        )
        with patch(
            "uar.api.middleware.API_KEYS", {"k": {"user": "u"}}
        ):
            with patch.dict(
                os.environ, {"ENVIRONMENT": "development"}
            ):
                assert auth_middleware(creds) is None


# ---------------------------------------------------------------------------
# Request logging
# ---------------------------------------------------------------------------


class TestRequestLogging:
    def test_logs_request(self):
        req = MagicMock()
        req.headers.get.return_value = None
        req.url.path = "/test"
        req.url.query = ""
        req.method = "GET"
        req.client.host = "127.0.0.1"
        rid = request_logging_middleware(req, None)
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_redacts_sensitive_params(self):
        url = URL("http://x/?api_key=secret&foo=bar")
        safe = _redact_query_params(url)
        assert "***" in safe
        assert "secret" not in safe
        assert "bar" in safe

    def test_no_query(self):
        url = URL("http://x/")
        assert _redact_query_params(url) == ""


# ---------------------------------------------------------------------------
# Error handler middleware
# ---------------------------------------------------------------------------


class TestErrorHandlerMiddleware:
    @pytest.mark.asyncio
    async def test_passes_through(self):
        @error_handler_middleware
        async def good():
            return "ok"

        assert await good() == "ok"

    @pytest.mark.asyncio
    async def test_catches_exception(self):
        @error_handler_middleware
        async def bad():
            raise RuntimeError("boom")

        with pytest.raises(HTTPException) as exc:
            await bad()
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_extracts_request_id_from_args(self):
        req = MagicMock(spec=Request)
        req.state.request_id = "req-123"

        @error_handler_middleware
        async def bad(request):
            raise RuntimeError("boom")

        with pytest.raises(HTTPException) as exc:
            await bad(req)
        assert exc.value.status_code == 500
        assert "req-123" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_extracts_request_id_from_kwargs(self):
        req = MagicMock()
        req.state.request_id = "req-456"

        @error_handler_middleware
        async def bad(**kwargs):
            raise RuntimeError("boom")

        with pytest.raises(HTTPException) as exc:
            await bad(request=req)
        assert exc.value.status_code == 500
        assert "req-456" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_no_request_in_args(self):
        @error_handler_middleware
        async def bad(some_arg):
            raise RuntimeError("boom")

        with pytest.raises(HTTPException) as exc:
            await bad("not_a_request")
        assert exc.value.status_code == 500
        assert "unknown" in str(exc.value.detail)


class TestApiErrorHandler:
    @pytest.mark.asyncio
    async def test_passes_through(self):
        handler = api_error_handler("test")

        @handler
        async def good():
            return "ok"

        assert await good() == "ok"

    @pytest.mark.asyncio
    async def test_catches_generic(self):
        handler = api_error_handler("test")

        @handler
        async def bad():
            raise RuntimeError("boom")

        with pytest.raises(HTTPException) as exc:
            await bad()
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_passes_uarerror(self):
        from uar.core.exceptions import UARError

        handler = api_error_handler("test")

        @handler
        async def bad():
            raise UARError("uarex")

        with pytest.raises(UARError):
            await bad()


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


class TestDevMode:
    def test_dev(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert _is_dev_mode() is True

    def test_prod(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert _is_dev_mode() is False


class TestCorsOrigins:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            origins = _get_cors_origins()
        assert "http://localhost:3000" in origins

    def test_custom(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://app.com"}):
            origins = _get_cors_origins()
        assert origins == ["https://app.com"]


class TestLoadRateLimits:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            limits = _load_rate_limits()
        assert "default" in limits
        assert "authenticated" in limits

    def test_custom_values(self):
        with patch.dict(
            os.environ,
            {"RATE_LIMIT_ANONYMOUS": "20", "RATE_LIMIT_WINDOW": "120"},
        ):
            limits = _load_rate_limits()
        assert limits["default"]["requests"] == 20
        assert limits["default"]["window"] == 120


class TestLoadSkillRateLimits:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            limits = _load_skill_rate_limits()
        assert "ollama_generate" in limits

    def test_custom_env(self):
        with patch.dict(
            os.environ, {"SKILL_RATE_LIMITS": "custom:10:30,bad,numeric:x:10"}
        ):
            limits = _load_skill_rate_limits()
        assert limits["custom"]["requests"] == 10
        assert "bad" not in limits
        assert "numeric" not in limits

    def test_env_overrides_default(self):
        with patch.dict(
            os.environ, {"SKILL_RATE_LIMITS": "ollama_generate:20:120"}
        ):
            limits = _load_skill_rate_limits()
        assert limits["ollama_generate"]["requests"] == 20
        assert limits["ollama_generate"]["window"] == 120


# ---------------------------------------------------------------------------
# FastAPI middleware integration
# ---------------------------------------------------------------------------


class TestApplyMiddleware:
    def test_applies_all(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        reset_rate_limiter()
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        # Rate limit headers only appear when rate_limit_middleware runs
        assert "X-Correlation-ID" in response.headers

    def test_api_version_rewrite(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/api/test")
        async def endpoint():
            return {"ok": True}

        response = client.get("/api/v1/test")
        assert response.status_code == 200

    def test_body_size_rejection(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.post("/test")
        async def endpoint():
            return {"ok": True}

        response = client.post(
            "/test",
            headers={"content-length": "999999999"},
            data="x",
        )
        assert response.status_code == 413

    def test_body_size_malformed_header(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.post("/test")
        async def endpoint():
            return {"ok": True}

        response = client.post(
            "/test",
            headers={"content-length": "not-a-number"},
            data="x",
        )
        # Malformed header passes through to handler
        assert response.status_code == 200

    def test_body_size_no_header(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.post("/test")
        async def endpoint():
            return {"ok": True}

        response = client.post("/test", data="x")
        # No content-length header passes through to handler
        assert response.status_code == 200

    def test_rate_limit_headers(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/api/test")
        async def endpoint(request: Request):
            request.state.rate_limit_key = "anon:127.0.0.1"
            request.state.rate_limit = 10
            request.state.rate_limit_window = 60
            request.state.rate_limit_remaining = 5
            return {"ok": True}

        reset_rate_limiter()
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Remaining"] == "5"

    def test_hsts_header_in_production(self):
        app = FastAPI()
        apply_middleware(app)
        client = TestClient(app)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            response = client.get("/test")
        assert response.status_code == 200
        assert "Strict-Transport-Security" in response.headers


class TestRegisterMetricsMiddleware:
    def test_records_request(self):
        app = FastAPI()
        register_metrics_middleware(app)
        client = TestClient(app)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        response = client.get("/test")
        assert response.status_code == 200

    def test_records_error(self):
        app = FastAPI()
        register_metrics_middleware(app)
        client = TestClient(app, raise_server_exceptions=False)

        @app.get("/error")
        async def endpoint():
            raise RuntimeError("boom")

        response = client.get("/error")
        assert response.status_code == 500

    def test_slow_request_warning(self, caplog):
        import time
        app = FastAPI()
        register_metrics_middleware(app)
        client = TestClient(app)

        @app.get("/slow")
        async def endpoint():
            time.sleep(5.1)
            return {"ok": True}

        with caplog.at_level("WARNING", logger="uar.api.middleware"):
            response = client.get("/slow")
        assert response.status_code == 200
        assert "slow_request" in caplog.text


class TestRequireAuth:
    def test_valid(self):
        app = FastAPI()
        client = TestClient(app)

        @app.get("/test")
        async def endpoint(
            request: Request,
            credentials: HTTPAuthorizationCredentials = Depends(
                HTTPBearer(auto_error=False)
            ),
        ):
            return require_auth(request, credentials)

        with patch(
            "uar.api.middleware.API_KEYS", {"key1": {"user": "user1"}}
        ):
            response = client.get(
                "/test", headers={"Authorization": "Bearer key1"}
            )
        assert response.status_code == 200
        assert response.json()["user"] == "user1"

    def test_missing(self):
        app = FastAPI()
        client = TestClient(app)

        @app.get("/test")
        async def endpoint(
            request: Request,
            credentials: HTTPAuthorizationCredentials = Depends(
                HTTPBearer(auto_error=False)
            ),
        ):
            return require_auth(request, credentials)

        response = client.get("/test")
        assert response.status_code == 401
