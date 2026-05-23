"""Tests for the rate-limiter factory (create_rate_limiter).

Covers: Redis default in production, fallback in dev, hard failures.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from uar.api.middleware import (
    RateLimiter,
    RedisRateLimiter,
    create_rate_limiter,
)


class TestCreateRateLimiter:
    def test_dev_without_redis_uses_in_memory(self):
        """Development mode without REDIS_URL falls back to in-memory."""
        env = {"ENVIRONMENT": "development"}
        with mock.patch.dict(os.environ, env, clear=True):
            rl = create_rate_limiter()
            assert isinstance(rl, RateLimiter)
            assert not isinstance(rl, RedisRateLimiter)

    def test_production_without_redis_raises(self):
        """Production mode without REDIS_URL must fail hard."""
        env = {"ENVIRONMENT": "production"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="requires REDIS_URL"):
                create_rate_limiter()

    def test_production_with_redis_url_uses_redis(self):
        """Production with REDIS_URL creates RedisRateLimiter.

        If redis package is missing, it must raise in production.
        """
        env = {"ENVIRONMENT": "production", "REDIS_URL": "redis://x:6379/0"}
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                import redis as _redis  # noqa: F401
            except ImportError:
                with pytest.raises(RuntimeError, match="redis package"):
                    create_rate_limiter()
                return

            # redis package installed — RedisRateLimiter is created
            # (connection is lazy; actual Redis ops fail at runtime)
            rl = create_rate_limiter()
            assert isinstance(rl, RedisRateLimiter)

    def test_redis_url_set_dev_uses_redis(self):
        """Development mode with REDIS_URL also uses RedisRateLimiter."""
        env = {
            "ENVIRONMENT": "development",
            "REDIS_URL": "redis://unreachable-host:6379/0",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                rl = create_rate_limiter()
            except RuntimeError:
                pytest.skip("redis package not installed")
            assert isinstance(rl, RedisRateLimiter)
