"""Tests for uar.core.cache."""

from unittest.mock import patch

import uar.core.cache as cache_module
from uar.core.cache import clear_global_cache, get_cache


class TestGetCache:
    def _reset(self):
        cache_module._global_cache = None

    def test_get_cache_returns_instance(self):
        self._reset()
        cache = get_cache()
        assert cache is not None

    def test_get_cache_same_instance(self):
        self._reset()
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_invalid_ttl_fallback(self):
        self._reset()
        with patch.dict("os.environ", {"UAR_CACHE_TTL": "not_a_number"}):
            cache = get_cache()
            assert cache is not None

    def test_invalid_max_entries_fallback(self):
        self._reset()
        with patch.dict("os.environ", {"UAR_CACHE_MAX_ENTRIES": "bad"}):
            cache = get_cache()
            assert cache is not None

    def test_invalid_max_size_fallback(self):
        self._reset()
        with patch.dict("os.environ", {"UAR_CACHE_MAX_SIZE": "invalid"}):
            cache = get_cache()
            assert cache is not None


class TestClearGlobalCache:
    def _reset(self):
        cache_module._global_cache = None

    def test_clear_without_skill(self):
        self._reset()
        cache = get_cache()
        cache.set("test_skill", {}, {}, "value")
        clear_global_cache()

    def test_clear_with_skill(self):
        self._reset()
        cache = get_cache()
        cache.set("test_skill", {}, {}, "value")
        clear_global_cache(skill_name="test_skill")
