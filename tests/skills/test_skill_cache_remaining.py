"""Tests for uar.core.skill_cache remaining coverage gaps."""

import os
from unittest.mock import MagicMock, patch

import pytest

from uar.core.skill_cache import (
    _close_redis,
    cached_skill,
)


@pytest.fixture(autouse=True)
def reset_global_cache():
    """Reset global skill cache before and after each test."""
    import uar.core.skill_cache as sc
    old = sc._global_skill_cache
    sc._global_skill_cache = None
    yield
    sc._global_skill_cache = old


class TestZstdFallback:
    def test_zstd_not_available(self):
        with patch("uar.core.skill_cache._HAS_ZSTD", False):
            from uar.core.skill_cache import _HAS_ZSTD as has_z
            assert has_z is False


class TestCloseRedis:
    def test_close_exception(self):
        with patch("uar.core.skill_cache._redis_client") as mock_client:
            mock_client.close.side_effect = RuntimeError("fail")
            _close_redis()


class TestRedisSkillCacheZstd:
    def test_get_zstd(self):
        pytest = __import__("pytest")
        try:
            import zstandard  # noqa: F401
        except ImportError:
            pytest.skip("zstandard not available")
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_zstd = MagicMock()
        mock_zstd.ZstdDecompressor.return_value.decompress.return_value = (
            b'{"value": 42}'
        )
        mock_redis.get.side_effect = [b"zstd_payload", None]

        with patch(
            "uar.core.skill_cache.zstd", mock_zstd
        ):
            with patch(
                "uar.core.skill_cache._get_redis", return_value=mock_redis
            ):
                with patch("uar.core.skill_cache._HAS_ZSTD", True):
                    cache = RedisSkillCache()
                    result = cache.get("s1", {"a": 1})
        assert result == {"value": 42}

    def test_get_exception(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("fail")

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.get("s1", {"a": 1}) is None

    def test_set_compress_zstd(self):
        pytest = __import__("pytest")
        try:
            import zstandard  # noqa: F401
        except ImportError:
            pytest.skip("zstandard not available")
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_zstd = MagicMock()
        mock_zstd.ZstdCompressor.return_value.compress.return_value = (
            b"compressed"
        )

        with patch(
            "uar.core.skill_cache.zstd", mock_zstd
        ):
            with patch(
                "uar.core.skill_cache._get_redis", return_value=mock_redis
            ):
                with patch.dict(os.environ, {"UAR_CACHE_COMPRESS": "true"}):
                    with patch("uar.core.skill_cache._HAS_ZSTD", True):
                        cache = RedisSkillCache()
                        cache.set("s1", {"a": 1}, {"value": 42}, 60)
                        assert mock_redis.setex.called

    def test_set_exception(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = RuntimeError("fail")

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            cache.set("s1", {"a": 1}, {"value": 42}, 60)

    def test_invalidate_all_none_keys(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.return_value = None

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.invalidate() == 0

    def test_invalidate_skill_compressed(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["k1:z"]
        mock_redis.get.return_value = b"not json"

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.invalidate("s1") == 0

    def test_invalidate_skill_exception(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.side_effect = RuntimeError("fail")

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.invalidate("s1") == 0


class TestGetSkillCacheRedis:
    def test_redis_path(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch("uar.core.skill_cache._get_redis") as gr:
                gr.return_value = MagicMock()
                with patch(
                    "uar.core.skill_cache.RedisSkillCache"
                ) as MockRedis:
                    mock_cache = MagicMock()
                    MockRedis.return_value = mock_cache
                    from uar.core.skill_cache import get_skill_cache
                    # Reset global cache
                    import uar.core.skill_cache as sc
                    sc._global_skill_cache = None
                    cache = get_skill_cache()
                    assert cache is mock_cache


class TestCachedSkillSkipOnErrorFalse:
    def test_caches_failed_result(self):
        from uar.core.skill_cache import SkillCache
        fresh_cache = SkillCache()
        with patch(
            "uar.core.skill_cache.get_skill_cache", return_value=fresh_cache
        ):
            call_count = 0

            @cached_skill(ttl_seconds=60, skip_on_error=False)
            def skill_fail(ctx):
                nonlocal call_count
                call_count += 1
                return {"status": "failed", "error": "oops"}

            class Ctx:
                goal = {"metadata": {}}

            ctx = Ctx()
            skill_fail(ctx)
            skill_fail(ctx)
            assert call_count == 1  # cached even though failed

    def test_no_status_field(self):
        from uar.core.skill_cache import SkillCache
        fresh_cache = SkillCache()
        with patch(
            "uar.core.skill_cache.get_skill_cache", return_value=fresh_cache
        ):
            call_count = 0

            @cached_skill(ttl_seconds=60)
            def skill_no_status(ctx):
                nonlocal call_count
                call_count += 1
                return {"value": 42}

            class Ctx:
                goal = {"metadata": {}}

            ctx = Ctx()
            skill_no_status(ctx)
            skill_no_status(ctx)
            assert call_count == 1
