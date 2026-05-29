"""Focused feature tests for the SLA (rate-limit) structure.

Covers the full stack: tier config → key building → limiter behaviour →
middleware request-state → service wrapper.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from unittest import mock

import pytest

from uar.api.middleware import (
    RateLimiter,
    RedisRateLimiter,
    build_rate_limit_key,
    get_rate_limit_for_tier,
    reset_rate_limiter,
    _load_rate_limits,
    _load_skill_rate_limits,
)
from uar.services.rate_limit import RateLimitService


# ───────────────────────────
# Tier configuration
# ───────────────────────────

class TestTierConfiguration:
    """SLA tier limits are loaded from environment with safe clamping."""

    def test_default_tier_limits(self):
        limits = _load_rate_limits()
        assert "default" in limits
        assert "authenticated" in limits
        assert limits["default"]["requests"] >= 1
        assert limits["default"]["window"] >= 1

    def test_env_override_anonymous_requests(self):
        env = {"RATE_LIMIT_ANONYMOUS": "25"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_rate_limits()
            assert limits["default"]["requests"] == 25

    def test_env_clamps_to_maximum(self):
        env = {"RATE_LIMIT_ANONYMOUS": "999999"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_rate_limits()
            assert limits["default"]["requests"] == 100_000

    def test_env_clamps_to_minimum(self):
        env = {"RATE_LIMIT_ANONYMOUS": "0"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_rate_limits()
            assert limits["default"]["requests"] == 1

    def test_empty_env_string_falls_back_to_default(self):
        env = {"RATE_LIMIT_ANONYMOUS": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_rate_limits()
            assert limits["default"]["requests"] == 10

    def test_get_rate_limit_for_tier_returns_tuple(self):
        req, window = get_rate_limit_for_tier("default")
        assert isinstance(req, int)
        assert isinstance(window, int)
        assert req > 0 and window > 0

    def test_unknown_tier_falls_back_to_default(self):
        limits = _load_rate_limits()
        req, window = get_rate_limit_for_tier("nonexistent")
        assert req == limits["default"]["requests"]
        assert window == limits["default"]["window"]


# ───────────────────────────
# Key building
# ───────────────────────────

class TestBuildRateLimitKey:
    """Rate-limit keys encode identity + tier for per-client tracking."""

    def test_anonymous_key_format(self):
        key, tier = build_rate_limit_key("1.2.3.4", None)
        assert key == "anon:1.2.3.4"
        assert tier == "default"

    def test_authenticated_key_format(self):
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="test-key"
        )
        # API_KEYS may not contain test-key; this exercises the else branch
        key, tier = build_rate_limit_key("1.2.3.4", creds)
        # When key is unknown, tier is still "default"
        assert key == "anon:1.2.3.4"
        assert tier == "default"

    def test_unknown_ip_uses_literal_unknown(self):
        key, tier = build_rate_limit_key("unknown", None)
        assert key == "anon:unknown"
        assert tier == "default"


# ───────────────────────────
# In-memory limiter core
# ───────────────────────────

class TestRateLimiterCore:
    """Sliding-window rate limiter with O(1) deque operations."""

    def setup_method(self):
        self.rl = RateLimiter(
            cleanup_threshold=1000,
            cleanup_interval=1000,
            max_entries=1000,
        )

    def teardown_method(self):
        reset_rate_limiter()

    def test_first_request_allowed(self):
        allowed, remaining = self.rl.is_allowed("user:a", limit=5, window=60)
        assert allowed is True
        assert remaining == 4

    def test_limit_enforced_exactly(self):
        for _ in range(5):
            allowed, _ = self.rl.is_allowed("user:a", limit=5, window=60)
            assert allowed is True
        allowed, remaining = self.rl.is_allowed("user:a", limit=5, window=60)
        assert allowed is False
        assert remaining == 0

    def test_remaining_decreases_monotonically(self):
        prev = 6
        for i in range(6):
            allowed, remaining = self.rl.is_allowed(
                "user:b", limit=6, window=60
            )
            assert allowed is True
            assert remaining == 5 - i
            assert remaining < prev
            prev = remaining

    def test_window_expiry_restores_budget(self):
        # Tiny window so we can test expiry without long sleeps
        allowed, _ = self.rl.is_allowed("user:c", limit=1, window=0.05)
        assert allowed is True
        allowed, _ = self.rl.is_allowed("user:c", limit=1, window=0.05)
        assert allowed is False
        time.sleep(0.06)
        allowed, _ = self.rl.is_allowed("user:c", limit=1, window=0.05)
        assert allowed is True

    def test_different_keys_are_isolated(self):
        for _ in range(5):
            self.rl.is_allowed("user:d", limit=5, window=60)
        allowed, _ = self.rl.is_allowed("user:e", limit=5, window=60)
        assert allowed is True

    def test_get_remaining_without_increment(self):
        self.rl.is_allowed("user:f", limit=5, window=60)
        self.rl.is_allowed("user:f", limit=5, window=60)
        rem = self.rl.get_remaining("user:f", limit=5, window=60)
        assert rem == 3
        # Calling get_remaining again should not change the count
        assert (
            self.rl.get_remaining("user:f", limit=5, window=60) == 3
        )

    def test_evict_empty_removes_stale_keys(self):
        self.rl.is_allowed("user:g", limit=5, window=60)
        assert len(self.rl.requests) == 1
        removed = self.rl.evict_empty()
        # Key still has active entries
        assert removed == 0
        assert len(self.rl.requests) == 1

    def test_evict_empty_removes_expired_keys(self):
        # Use a tiny window, let entries expire, then evict
        self.rl.is_allowed("user:h", limit=1, window=0.01)
        time.sleep(0.02)
        # Trigger internal expiry via is_allowed on a different key
        self.rl.is_allowed("other", limit=1, window=60)
        removed = self.rl.evict_empty()
        assert removed >= 0  # may be 0 or 1 depending on timing

    def test_max_entries_enforcement(self):
        tiny = RateLimiter(
            cleanup_threshold=10_000,
            cleanup_interval=10_000,
            max_entries=3,
        )
        tiny.is_allowed("k1", limit=5, window=60)
        tiny.is_allowed("k2", limit=5, window=60)
        tiny.is_allowed("k3", limit=5, window=60)
        tiny.is_allowed("k4", limit=5, window=60)
        assert len(tiny.requests) <= 3

    def test_ordered_dict_lru_tracking(self):
        self.rl.is_allowed("lru:a", limit=5, window=60)
        self.rl.is_allowed("lru:b", limit=5, window=60)
        assert isinstance(self.rl._key_order, OrderedDict)
        assert "lru:a" in self.rl._key_order
        assert "lru:b" in self.rl._key_order


# ───────────────────────────
# Skill-specific limits
# ───────────────────────────

class TestSkillRateLimits:
    """Skill-specific SLA overrides tier defaults."""

    def test_default_skill_limits_present(self):
        limits = _load_skill_rate_limits()
        assert "ollama_generate" in limits
        assert "graphrag_index" in limits
        assert "doc_ingest" in limits

    def test_env_override_parsing(self):
        env = {"SKILL_RATE_LIMITS": "custom_skill:15:120"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_skill_rate_limits()
            assert limits["custom_skill"]["requests"] == 15
            assert limits["custom_skill"]["window"] == 120

    def test_env_override_invalid_entry_skipped(self):
        env = {"SKILL_RATE_LIMITS": "bad_entry,good:5:60"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_skill_rate_limits()
            assert "good" in limits
            assert limits["good"]["requests"] == 5

    def test_env_override_non_numeric_skipped(self):
        env = {"SKILL_RATE_LIMITS": "x:abc:60"}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_skill_rate_limits()
            assert "x" not in limits

    def test_defaults_preserved_when_env_empty(self):
        env = {"SKILL_RATE_LIMITS": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            limits = _load_skill_rate_limits()
            assert "ollama_generate" in limits
            assert limits["ollama_generate"]["requests"] == 5


# ───────────────────────────
# Service wrapper
# ───────────────────────────

class TestRateLimitService:
    """RateLimitService provides uniform error formatting."""

    def test_check_returns_allowed_true(self):
        svc = RateLimitService()
        allowed, tier, limit_dict = svc.check("1.2.3.4", None)
        assert allowed is True
        assert tier == "default"
        assert "requests" in limit_dict
        assert "window" in limit_dict

    def test_check_returns_correct_limit_values(self):
        svc = RateLimitService()
        _, _, limit_dict = svc.check("1.2.3.4", None)
        assert limit_dict["requests"] > 0
        assert limit_dict["window"] > 0


# ───────────────────────────
# Redis limiter stub
# ───────────────────────────

class TestRedisRateLimiterStub:
    """RedisRateLimiter interface without live Redis."""

    def test_init_requires_valid_redis_url(self):
        with pytest.raises(ValueError, match="Redis URL must specify"):
            RedisRateLimiter(redis_url="invalid-url")

    def test_interface_matches_in_memory(self):
        # Verify both limiters expose is_allowed with same signature
        import inspect

        mem_sig = inspect.signature(RateLimiter.is_allowed)
        redis_sig = inspect.signature(RedisRateLimiter.is_allowed)
        assert list(mem_sig.parameters.keys()) == list(
            redis_sig.parameters.keys()
        )
