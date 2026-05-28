"""Tests for uar.core.skill_cache."""

import time
from unittest.mock import MagicMock

import pytest

from uar.core.skill_cache import SkillCache, cached_skill


@pytest.fixture(autouse=True)
def clear_global_skill_cache():
    """Clear global skill cache between tests to ensure isolation."""
    yield
    # After each test, clear any cached entries from the global cache
    import uar.core.skill_cache as _sc

    if _sc._global_skill_cache is not None:
        _sc._global_skill_cache.invalidate()


class TestSkillCache:
    def test_make_key_deterministic(self):
        cache = SkillCache()
        k1 = cache._make_key("math", {"x": 1})
        k2 = cache._make_key("math", {"x": 1})
        assert k1 == k2

    def test_different_inputs_different_keys(self):
        cache = SkillCache()
        k1 = cache._make_key("math", {"x": 1})
        k2 = cache._make_key("math", {"x": 2})
        assert k1 != k2

    def test_get_missing_returns_none(self):
        cache = SkillCache()
        assert cache.get("math", {}) is None

    def test_set_and_get(self):
        cache = SkillCache()
        cache.set("math", {"x": 1}, 42, ttl_seconds=300)
        assert cache.get("math", {"x": 1}) == 42

    def test_expiration(self):
        cache = SkillCache()
        cache.set("math", {"x": 1}, 42, ttl_seconds=0.01)
        assert cache.get("math", {"x": 1}) == 42
        time.sleep(0.02)
        assert cache.get("math", {"x": 1}) is None

    def test_invalidate_all(self):
        cache = SkillCache()
        cache.set("math", {"x": 1}, 1, 300)
        cache.set("doc", {"y": 2}, 2, 300)
        assert cache.invalidate() == 2
        assert cache.get("math", {"x": 1}) is None

    def test_invalidate_by_skill(self):
        cache = SkillCache()
        cache.set("math", {}, 1, 300)
        cache.set("doc", {}, 2, 300)
        assert cache.invalidate("math") == 1
        assert cache.get("math", {}) is None
        assert cache.get("doc", {}) == 2

    def test_stats(self):
        cache = SkillCache()
        cache.set("math", {}, 1, 300)
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["skills"] == ["math"]

    def test_maxsize_eviction(self):
        cache = SkillCache(maxsize=2)
        cache.set("a", {}, 1, 300)
        cache.set("b", {}, 2, 300)
        cache.set("c", {}, 3, 300)
        # At least one old entry was evicted
        assert cache.stats()["size"] <= 2


class TestCachedSkillDecorator:
    def test_caches_result(self):
        call_count = 0

        @cached_skill(ttl_seconds=60)
        def my_skill(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "completed", "value": 42}

        mock_ctx = MagicMock()
        mock_ctx.goal = MagicMock()
        mock_ctx.goal.metadata = {}

        r1 = my_skill(mock_ctx)
        r2 = my_skill(mock_ctx)

        assert r1 == r2
        assert call_count == 1

    def test_does_not_cache_failed_status(self):
        call_count = 0

        @cached_skill(ttl_seconds=60)
        def failing_skill(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "failed", "error": "oops"}

        mock_ctx = MagicMock()
        mock_ctx.goal = MagicMock()
        mock_ctx.goal.metadata = {}

        failing_skill(mock_ctx)
        failing_skill(mock_ctx)
        assert call_count == 2

    def test_caches_failed_when_skip_disabled(self):
        call_count = 0

        @cached_skill(ttl_seconds=60, skip_on_error=False)
        def failing_skill(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "failed", "error": "oops"}

        mock_ctx = MagicMock()
        mock_ctx.goal = MagicMock()
        mock_ctx.goal.metadata = {}

        failing_skill(mock_ctx)
        failing_skill(mock_ctx)
        assert call_count == 1

    def test_cache_invalidate_method(self):
        call_count = 0

        @cached_skill(ttl_seconds=60)
        def invalidate_test_skill(ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "completed", "value": 1}

        mock_ctx = MagicMock()
        mock_ctx.goal = MagicMock()
        mock_ctx.goal.metadata = {}

        invalidate_test_skill(mock_ctx)
        invalidate_test_skill(mock_ctx)
        assert call_count == 1  # cached
        invalidate_test_skill.cache_invalidate()
        invalidate_test_skill(mock_ctx)
        assert call_count == 2  # re-executed after invalidate
