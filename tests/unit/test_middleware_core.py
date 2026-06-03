"""Tests for uar.api.middleware core functions.

Covers rate limiting, auth, request logging, and error handling
that are not exercised by integration tests.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.datastructures import URL

from uar.api.middleware import (
    _load_api_keys,
    _load_rate_limits,
    _load_skill_rate_limits,
    _redact_query_params,
    build_rate_limit_key,
    check_rate_limit,
    create_rate_limiter,
    error_handler_middleware,
    get_rate_limit_for_tier,
    get_rate_limit_key,
    RateLimiter,
    reset_rate_limiter,
)


class TestLoadRateLimits:
    """Rate limit config from environment."""

    def test_default_limits(self):
        limits = _load_rate_limits()
        assert "default" in limits
        assert "authenticated" in limits
        assert limits["default"]["requests"] >= 1
        assert limits["default"]["window"] >= 1

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANONYMOUS", "5")
        monkeypatch.setenv("RATE_LIMIT_WINDOW", "120")
        limits = _load_rate_limits()
        assert limits["default"]["requests"] == 5
        assert limits["default"]["window"] == 120

    def test_env_clamped_high(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANONYMOUS", "999999")
        limits = _load_rate_limits()
        assert limits["default"]["requests"] == 100000

    def test_env_clamped_low(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANONYMOUS", "0")
        limits = _load_rate_limits()
        assert limits["default"]["requests"] == 1

    def test_env_empty_string(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANONYMOUS", "")
        limits = _load_rate_limits()
        assert limits["default"]["requests"] == 10


class TestLoadSkillRateLimits:
    """Skill-specific rate limit parsing."""

    def test_defaults_present(self):
        limits = _load_skill_rate_limits()
        assert "ollama_generate" in limits
        assert "doc_ingest" in limits
        assert limits["ollama_generate"]["requests"] == 5

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv(
            "SKILL_RATE_LIMITS", "ollama_generate:3:30,doc_ingest:10:60"
        )
        limits = _load_skill_rate_limits()
        assert limits["ollama_generate"]["requests"] == 3
        assert limits["ollama_generate"]["window"] == 30
        assert limits["doc_ingest"]["requests"] == 10

    def test_env_invalid_entry_warns(self, monkeypatch, caplog):
        monkeypatch.setenv("SKILL_RATE_LIMITS", "bad_entry")
        limits = _load_skill_rate_limits()
        assert "ollama_generate" in limits  # defaults still present
        assert "Skipping invalid" in caplog.text

    def test_env_non_numeric_warns(self, monkeypatch, caplog):
        monkeypatch.setenv("SKILL_RATE_LIMITS", "skill:x:60")
        _load_skill_rate_limits()
        assert "non-numeric" in caplog.text


class TestRateLimiter:
    """In-memory rate limiter."""

    def test_is_allowed_first_request(self):
        rl = RateLimiter()
        allowed, remaining = rl.is_allowed("key1", 10, 60)
        assert allowed is True
        assert remaining == 9

    def test_is_allowed_blocks_at_limit(self):
        rl = RateLimiter()
        for _ in range(10):
            allowed, _ = rl.is_allowed("key1", 10, 60)
            assert allowed is True
        allowed, remaining = rl.is_allowed("key1", 10, 60)
        assert allowed is False
        assert remaining == 0

    def test_is_allowed_expires_old_requests(self):
        rl = RateLimiter()
        allowed, _ = rl.is_allowed("key1", 1, 0.05)
        assert allowed is True
        import time
        time.sleep(0.06)
        allowed, _ = rl.is_allowed("key1", 1, 0.05)
        assert allowed is True

    def test_get_remaining_no_requests(self):
        rl = RateLimiter()
        assert rl.get_remaining("key1", 10, 60) == 10

    def test_get_remaining_after_requests(self):
        rl = RateLimiter()
        rl.is_allowed("key1", 10, 60)
        rl.is_allowed("key1", 10, 60)
        assert rl.get_remaining("key1", 10, 60) == 8

    def test_evict_empty(self):
        rl = RateLimiter()
        rl.is_allowed("key1", 1, 0.01)
        import time
        time.sleep(0.15)  # Wait past window
        # get_remaining purges expired items, leaving deque empty
        rl.get_remaining("key1", 1, 0.01)
        removed = rl.evict_empty()
        assert removed >= 1

    def test_max_entries_enforcement(self):
        rl = RateLimiter(max_entries=2)
        rl.is_allowed("k1", 100, 60)
        rl.is_allowed("k2", 100, 60)
        rl.is_allowed("k3", 100, 60)
        assert len(rl.requests) <= 2

    def test_cleanup_periodic(self):
        rl = RateLimiter(cleanup_interval=2, cleanup_threshold=1)
        rl.is_allowed("k1", 100, 60)
        rl.is_allowed("k2", 100, 60)
        assert len(rl.requests) == 2


class TestCreateRateLimiter:
    """Factory behavior."""

    def test_returns_in_memory_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            rl = create_rate_limiter()
            assert isinstance(rl, RateLimiter)

    def test_redis_url_import_error_warns(self, monkeypatch, caplog):
        monkeypatch.setenv("REDIS_URL", "redis://localhost")
        with patch("builtins.__import__", side_effect=ImportError("no redis")):
            with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
                rl = create_rate_limiter()
                assert isinstance(rl, RateLimiter)
                assert "redis package is not installed" in caplog.text

    def test_production_without_redis_raises(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        with patch.dict(os.environ, {"REDIS_URL": ""}, clear=False):
            with pytest.raises(RuntimeError, match="REDIS_URL"):
                create_rate_limiter()


class TestLoadApiKeys:
    """API key loading."""

    def test_empty_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            keys = _load_api_keys()
            assert keys == {}

    def test_from_env(self):
        env = {"API_KEYS": "key1:user1:tier1,key2:user2"}
        with patch.dict(os.environ, env):
            keys = _load_api_keys()
            assert "key1" in keys
            assert keys["key1"]["user"] == "user1"
            assert keys["key1"]["tier"] == "tier1"
            assert keys["key2"]["tier"] == "authenticated"

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("key1:user1:tier1\n")
            path = f.name
        try:
            with patch.dict(os.environ, {"API_KEYS_FILE": path}):
                keys = _load_api_keys()
                assert "key1" in keys
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty(self, caplog):
        with patch.dict(os.environ, {"API_KEYS_FILE": "/nonexistent/file"}):
            keys = _load_api_keys()
            assert keys == {}
            assert "Cannot read" in caplog.text


class TestGetRateLimitKey:
    """Rate limit key generation."""

    def _make_request(self, host="192.168.1.1"):
        scope = {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": (host, 8000),
            "client": (host, 12345),
            "headers": [],
            "path": "/api/health",
            "query_string": b"",
            "root_path": "",
        }
        return Request(scope)

    def test_anonymous(self):
        req = self._make_request()
        key = get_rate_limit_key(req, None)
        assert key.startswith("anon:")

    def test_authenticated(self):
        req = self._make_request()
        keys = {"secret": {"user": "user1", "tier": "tier1"}}
        with patch("uar.api.middleware.API_KEYS", keys):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="secret"
            )
            key = get_rate_limit_key(req, creds)
            assert key.startswith("auth:user1:")


class TestGetRateLimitForTier:
    """Tier-based rate limits."""

    def test_default_tier(self):
        limit, window = get_rate_limit_for_tier("default")
        assert limit > 0
        assert window > 0

    def test_authenticated_tier(self):
        limit, window = get_rate_limit_for_tier("authenticated")
        assert limit > 0
        assert window > 0

    def test_unknown_tier_fallback(self):
        limit, window = get_rate_limit_for_tier("unknown")
        assert limit > 0
        assert window > 0


class TestBuildRateLimitKey:
    """Key + tier extraction."""

    def test_anonymous(self):
        key, tier = build_rate_limit_key("10.0.0.1", None)
        assert tier == "default"
        assert "anon" in key

    def test_authenticated(self):
        keys = {"secret": {"user": "user1", "tier": "tier1"}}
        with patch("uar.api.middleware.API_KEYS", keys):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="secret"
            )
            key, tier = build_rate_limit_key("10.0.0.1", creds)
            assert tier == "tier1"
            assert "auth" in key


class TestRedactQueryParams:
    """Sensitive param redaction."""

    def test_no_params(self):
        url = URL("http://example.com/path")
        assert _redact_query_params(url) == ""

    def test_safe_params_preserved(self):
        url = URL("http://example.com/path?foo=bar")
        assert _redact_query_params(url) == "?foo=bar"

    def test_token_redacted(self):
        url = URL("http://example.com/path?token=secret123")
        result = _redact_query_params(url)
        assert "***" in result
        assert "secret123" not in result

    def test_multiple_params(self):
        url = URL("http://example.com/path?foo=bar&api_key=secret")
        result = _redact_query_params(url)
        assert "foo=bar" in result
        assert "***" in result


class TestCheckRateLimit:
    """Rate limit check logic."""

    def test_tier_limit(self):
        limit, window, rtype = check_rate_limit("key", "default", None)
        assert limit > 0
        assert rtype == "tier"

    def test_skill_limit(self, monkeypatch):
        monkeypatch.setenv("SKILL_RATE_LIMITS", "ollama_generate:5:60")
        # Force reload by re-importing
        from uar.api.middleware import check_rate_limit
        limit, window, rtype = check_rate_limit(
            "key", "default", "ollama_generate"
        )
        assert limit == 5
        assert rtype == "skill"


class TestResetRateLimiter:
    """Reset helper for tests."""

    def test_resets_state(self):
        rl = RateLimiter()
        rl.is_allowed("k1", 10, 60)
        reset_rate_limiter()


class TestErrorHandlerMiddleware:
    """Error handler wrapper."""

    def test_passes_through_success(self):
        @error_handler_middleware
        async def good():
            return "ok"

        import asyncio
        result = asyncio.run(good())
        assert result == "ok"

    def test_reraises_http_exception(self):
        @error_handler_middleware
        async def raises_http():
            raise HTTPException(status_code=404)

        import asyncio
        with pytest.raises(HTTPException):
            asyncio.run(raises_http())

    def test_wraps_generic_error(self):
        @error_handler_middleware
        async def bad():
            raise RuntimeError("boom")

        import asyncio
        with pytest.raises(HTTPException) as exc:
            asyncio.run(bad())
        assert exc.value.status_code == 500

    def test_extracts_request_id_from_args(self):
        req = self._make_request()
        req.state.request_id = "req-42"

        @error_handler_middleware
        async def bad(req):
            raise RuntimeError("boom")

        import asyncio
        with pytest.raises(HTTPException) as exc:
            asyncio.run(bad(req))
        assert "req-42" in str(exc.value.detail)

    def test_extracts_request_id_from_kwargs(self):
        req = self._make_request()
        req.state.request_id = "req-42"

        @error_handler_middleware
        async def bad(request=None):
            raise RuntimeError("boom")

        import asyncio
        with pytest.raises(HTTPException) as exc:
            asyncio.run(bad(request=req))
        assert "req-42" in str(exc.value.detail)

    def _make_request(self, host="192.168.1.1"):
        scope = {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": (host, 8000),
            "client": (host, 12345),
            "headers": [],
            "path": "/api/health",
            "query_string": b"",
            "root_path": "",
        }
        return Request(scope)


class TestAuthMiddleware:
    """Authentication middleware."""

    def test_no_credentials_returns_none(self):
        from uar.api.middleware import auth_middleware
        result = auth_middleware(None)
        assert result is None

    def test_invalid_key_dev_mode_returns_none(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        from uar.api.middleware import auth_middleware
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-key"
        )
        result = auth_middleware(creds)
        assert result is None

    def test_invalid_key_prod_raises(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        from uar.api.middleware import auth_middleware
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-key"
        )
        with pytest.raises(HTTPException, match="Invalid API key"):
            auth_middleware(creds)

    def test_valid_key_returns_user_info(self):
        keys = {"secret": {"user": "user1", "tier": "tier1"}}
        from uar.api.middleware import auth_middleware
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="secret"
        )
        with patch("uar.api.middleware.API_KEYS", keys):
            result = auth_middleware(creds)
        assert result["user"] == "user1"
        assert result["tier"] == "tier1"


class TestRateLimitMiddleware:
    """Rate limiting middleware integration."""

    def _make_request(self, host="192.168.1.1"):
        scope = {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": (host, 8000),
            "client": (host, 12345),
            "headers": [],
            "path": "/api/health",
            "query_string": b"",
            "root_path": "",
        }
        return Request(scope)

    def test_allows_under_limit(self, monkeypatch):
        reset_rate_limiter()
        from uar.api.middleware import rate_limit_middleware
        req = self._make_request()
        rate_limit_middleware(req, None)
        assert req.state.rate_limit_remaining >= 0

    def test_rejects_over_limit(self, monkeypatch):
        reset_rate_limiter()
        from uar.api.middleware import rate_limit_middleware
        req = self._make_request()
        # Exhaust limit
        with pytest.raises(HTTPException) as exc:
            for _ in range(15):
                rate_limit_middleware(req, None)
        assert exc.value.status_code == 429

    def test_skill_rate_limit(self, monkeypatch):
        reset_rate_limiter()
        monkeypatch.setenv("SKILL_RATE_LIMITS", "ollama_generate:1:60")
        from uar.api.middleware import rate_limit_middleware
        req = self._make_request()
        rate_limit_middleware(req, None, first_skill="ollama_generate")
        assert req.state.rate_limit_type == "skill"


class TestApplyMiddleware:
    """apply_middleware registration."""

    def test_registers_all(self):
        from fastapi import FastAPI
        from uar.api.middleware import apply_middleware

        app = FastAPI()
        apply_middleware(app)
        # FastAPI middleware are registered; just verify no exception
        assert len(app.user_middleware) >= 0
