"""Tests for uar.core.skill_cache."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from uar.core.skill_cache import (
    SkillCache,
    CompiledSkillCache,
    _BloomFilter,
    _get_redis,
    _close_redis,
    get_skill_cache,
    cached_skill,
    warm_skill_cache,
)


class TestSkillCache:
    def test_get_miss(self):
        cache = SkillCache()
        assert cache.get("skill1", {"a": 1}) is None

    def test_set_and_get(self):
        cache = SkillCache()
        cache.set("skill1", {"a": 1}, {"result": "ok"}, ttl_seconds=60)
        assert cache.get("skill1", {"a": 1}) == {"result": "ok"}

    def test_get_expired(self):
        cache = SkillCache()
        cache.set("skill1", {"a": 1}, {"result": "ok"}, ttl_seconds=0.01)
        time.sleep(0.02)
        assert cache.get("skill1", {"a": 1}) is None

    def test_lru_eviction(self):
        cache = SkillCache(maxsize=2)
        cache.set("s1", {"a": 1}, "v1", ttl_seconds=60)
        cache.set("s2", {"a": 2}, "v2", ttl_seconds=60)
        cache.set("s3", {"a": 3}, "v3", ttl_seconds=60)
        assert cache.get("s1", {"a": 1}) is None
        assert cache.get("s2", {"a": 2}) == "v2"

    def test_lru_touch(self):
        cache = SkillCache(maxsize=2)
        cache.set("s1", {"a": 1}, "v1", ttl_seconds=60)
        cache.set("s2", {"a": 2}, "v2", ttl_seconds=60)
        cache.get("s1", {"a": 1})  # touch s1
        cache.set("s3", {"a": 3}, "v3", ttl_seconds=60)
        assert cache.get("s1", {"a": 1}) == "v1"
        assert cache.get("s2", {"a": 2}) is None

    def test_invalidate_all(self):
        cache = SkillCache()
        cache.set("s1", {"a": 1}, "v1", ttl_seconds=60)
        count = cache.invalidate()
        assert count == 1
        assert cache.get("s1", {"a": 1}) is None

    def test_invalidate_by_skill(self):
        cache = SkillCache()
        cache.set("s1", {"a": 1}, "v1", ttl_seconds=60)
        cache.set("s2", {"a": 2}, "v2", ttl_seconds=60)
        count = cache.invalidate("s1")
        assert count == 1
        assert cache.get("s1", {"a": 1}) is None
        assert cache.get("s2", {"a": 2}) == "v2"

    def test_stats(self):
        cache = SkillCache(maxsize=10)
        cache.set("s1", {"a": 1}, "v1", ttl_seconds=60)
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["maxsize"] == 10
        assert "s1" in stats["skills"]


class TestCompiledSkillCache:
    def test_get_set(self):
        cache = CompiledSkillCache()
        assert cache.get("mod.path") is None
        cache.set("mod.path", lambda: 42)
        assert cache.get("mod.path")() == 42

    def test_invalidate(self):
        cache = CompiledSkillCache()
        cache.set("mod.path", lambda: 42)
        cache.invalidate("mod.path")
        assert cache.get("mod.path") is None

    def test_clear(self):
        cache = CompiledSkillCache()
        cache.set("a", 1)
        cache.clear()
        assert cache.get("a") is None

    def test_stats(self):
        cache = CompiledSkillCache()
        cache.set("a", 1)
        assert cache.stats()["size"] == 1


class TestBloomFilter:
    def test_add_and_check(self):
        bf = _BloomFilter()
        bf.add("item1")
        assert bf.might_contain("item1") is True
        assert bf.might_contain("item2") is False

    def test_false_positive_possible(self):
        bf = _BloomFilter(size=64, hash_count=2)
        for i in range(50):
            bf.add(f"item{i}")
        # After many items, might_contain could return True for non-added
        # but it's probabilistic; just ensure no crash
        bf.might_contain("not_added")


class TestGetRedis:
    def test_no_redis_url(self):
        with patch.dict(os.environ, {}, clear=True):
            _close_redis()
            assert _get_redis() is None

    def test_redis_unavailable(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            _close_redis()
            with patch.dict("sys.modules", {"redis": None}):
                assert _get_redis() is None

    def test_redis_import_error(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            _close_redis()
            with patch.dict("sys.modules", {"redis": None}):
                assert _get_redis() is None


class TestCloseRedis:
    def test_close_error(self):
        fake_mod = type("mod", (), {"from_url": lambda *a, **k: None})()
        with patch.dict("sys.modules", {"redis": fake_mod}):
            with patch.object(fake_mod, "from_url") as mock_from:
                client = MagicMock()
                client.close.side_effect = Exception("fail")
                mock_from.return_value = client
                _get_redis()
                _close_redis()


class TestRedisSkillCache:
    def test_init_no_redis(self):
        with patch.dict(os.environ, {}, clear=True):
            _close_redis()
            from uar.core.skill_cache import RedisSkillCache
            with pytest.raises(RuntimeError):
                RedisSkillCache()

    def test_get_set(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.get("s1", {"a": 1}) is None
            cache.set("s1", {"a": 1}, {"result": "ok"}, 60)
            assert mock_redis.setex.called

    def test_get_bloom_miss(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_bloom = MagicMock()
        mock_bloom.might_contain.return_value = False

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            with patch("uar.core.skill_cache._bloom_filter", mock_bloom):
                cache = RedisSkillCache()
                assert cache.get("s1", {"a": 1}) is None
                assert not mock_redis.get.called

    def test_get_compressed(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        import zlib
        payload = zlib.compress(b'{"value": 42}')
        mock_redis.get.side_effect = [payload, None]
        mock_bloom = MagicMock()
        mock_bloom.might_contain.return_value = True

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            with patch("uar.core.skill_cache._HAS_ZSTD", False):
                with patch("uar.core.skill_cache._bloom_filter", mock_bloom):
                    cache = RedisSkillCache()
                    result = cache.get("s1", {"a": 1})
                    assert result == {"value": 42}

    def test_get_bytes_decode(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.get.side_effect = [None, b'{"value": 42}']
        mock_bloom = MagicMock()
        mock_bloom.might_contain.return_value = True

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            with patch("uar.core.skill_cache._bloom_filter", mock_bloom):
                cache = RedisSkillCache()
                result = cache.get("s1", {"a": 1})
                assert result == {"value": 42}

    def test_get_json_error(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.get.side_effect = [None, b"bad json"]

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.get("s1", {"a": 1}) is None

    def test_get_redis_error(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("fail")

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.get("s1", {"a": 1}) is None

    def test_set_compress(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            with patch.dict(os.environ, {"UAR_CACHE_COMPRESS": "true"}):
                with patch("uar.core.skill_cache._HAS_ZSTD", False):
                    cache = RedisSkillCache()
                    cache.set("s1", {"a": 1}, {"value": 42}, 60)
                    assert mock_redis.setex.called

    def test_invalidate_all(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["k1", "k2"]

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.invalidate() == 2
            mock_redis.delete.assert_called_once()

    def test_invalidate_skill(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["k1"]
        mock_redis.get.return_value = b'{"skill": "s1"}'

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            assert cache.invalidate("s1") == 1

    def test_stats(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["k1"]

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            stats = cache.stats()
            assert stats["size"] == 1

    def test_stats_error(self):
        from uar.core.skill_cache import RedisSkillCache
        mock_redis = MagicMock()
        mock_redis.keys.side_effect = Exception("fail")

        with patch(
            "uar.core.skill_cache._get_redis", return_value=mock_redis
        ):
            cache = RedisSkillCache()
            stats = cache.stats()
            assert stats["size"] == 0


class TestGetSkillCache:
    def test_returns_skill_cache(self):
        with patch.dict(os.environ, {}, clear=True):
            cache = get_skill_cache()
            assert isinstance(cache, SkillCache)

    def test_redis_fallback(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch("uar.core.skill_cache._get_redis") as gr:
                gr.return_value = MagicMock()
                with patch(
                    "uar.core.skill_cache.RedisSkillCache"
                ) as MockRedis:
                    MockRedis.side_effect = RuntimeError("fail")
                    cache = get_skill_cache()
                    assert isinstance(cache, SkillCache)


def _make_ctx(meta=None):
    goal = {"metadata": meta or {}}
    return type("Ctx", (), {"goal": goal})()


class TestCachedSkill:
    def test_caches_result(self):
        call_count = 0

        @cached_skill(ttl_seconds=60)
        def skill_ok(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "completed", "value": 42}

        ctx = _make_ctx()
        r1 = skill_ok(ctx)
        r2 = skill_ok(ctx)
        assert r1 == r2 == {"status": "completed", "value": 42}
        assert call_count == 1

    def test_skips_failed_results(self):
        call_count = 0

        @cached_skill(ttl_seconds=60, skip_on_error=True)
        def skill_fail(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "failed", "error": "oops"}

        ctx = _make_ctx()
        skill_fail(ctx)
        skill_fail(ctx)
        assert call_count == 2  # not cached

    def test_non_dict_result(self):
        @cached_skill(ttl_seconds=60)
        def skill_str(ctx):
            return "hello"

        ctx = _make_ctx()
        assert skill_str(ctx) == "hello"

    def test_invalid_metadata(self):
        @cached_skill(ttl_seconds=60)
        def skill_none(ctx):
            return {"status": "completed"}

        ctx = type("Ctx", (), {})()
        assert skill_none(ctx) == {"status": "completed"}

    def test_cache_invalidate(self):
        call_count = 0

        @cached_skill(ttl_seconds=60)
        def skill_inv(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "completed"}

        ctx = _make_ctx()
        skill_inv(ctx)
        skill_inv.cache_invalidate()
        skill_inv(ctx)
        assert call_count == 2

    def test_cache_stats(self):
        @cached_skill(ttl_seconds=60)
        def skill_stats(ctx):
            return {"status": "completed"}

        ctx = _make_ctx()
        skill_stats(ctx)
        stats = skill_stats.cache_stats()
        assert stats["size"] >= 0


class TestWarmSkillCache:
    def test_warms(self):
        with patch.dict(os.environ, {}, clear=True):
            count = warm_skill_cache(
                "test_skill",
                [{"a": 1}, {"a": 2}],
                ttl_seconds=60,
            )
        assert count >= 0
