"""Tests for uar.core.analytics_cache."""

import time

from uar.core.analytics_cache import AnalyticsCache


class TestAnalyticsCache:
    def test_get_miss_returns_none(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        assert cache.get("ep", "u", False, 24, 1000) is None

    def test_set_then_get_returns_payload(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("ep", "u", False, 24, 1000, {"data": 42})
        assert cache.get("ep", "u", False, 24, 1000) == {"data": 42}

    def test_get_expired_returns_none(self):
        cache = AnalyticsCache(ttl_seconds=0.01)
        cache.set("ep", "u", False, 24, 1000, {"data": 42})
        time.sleep(0.02)
        assert cache.get("ep", "u", False, 24, 1000) is None

    def test_invalidate_all_clears_everything(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("a", "u1", False, 24, 1000, {"x": 1})
        cache.set("b", "u2", True, 168, 5000, {"y": 2})
        cache.invalidate()
        assert cache.get("a", "u1", False, 24, 1000) is None
        assert cache.get("b", "u2", True, 168, 5000) is None

    def test_invalidate_endpoint_removes_only_matching(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("a", "u1", False, 24, 1000, {"x": 1})
        cache.set("b", "u2", True, 168, 5000, {"y": 2})
        cache.invalidate("a")
        assert cache.get("a", "u1", False, 24, 1000) is None
        assert cache.get("b", "u2", True, 168, 5000) == {"y": 2}

    def test_key_scopes_by_all_params(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("ep", "u", False, 24, 1000, {"a": 1})
        cache.set("ep", "u", False, 24, 2000, {"a": 2})
        cache.set("ep", "u", True, 24, 1000, {"a": 3})
        cache.set("ep", "v", False, 24, 1000, {"a": 4})
        assert cache.get("ep", "u", False, 24, 1000) == {"a": 1}
        assert cache.get("ep", "u", False, 24, 2000) == {"a": 2}
        assert cache.get("ep", "u", True, 24, 1000) == {"a": 3}
        assert cache.get("ep", "v", False, 24, 1000) == {"a": 4}

    def test_stats(self):
        cache = AnalyticsCache(ttl_seconds=42.0)
        assert cache.stats() == {"entries": 0, "ttl_seconds": 42.0}
        cache.set("ep", "u", False, 24, 1000, {})
        assert cache.stats() == {"entries": 1, "ttl_seconds": 42.0}

    def test_integrity_verification_passes_intact_entry(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("ep", "u", False, 24, 1000, {"data": 42})
        assert cache.get("ep", "u", False, 24, 1000) == {"data": 42}

    def test_integrity_verification_treats_corrupt_as_miss(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("ep", "u", False, 24, 1000, {"data": 42})
        # Manually corrupt the stored payload
        with cache._lock:
            key = cache._key("ep", "u", False, 24, 1000)
            entry = cache._store[key]
            entry.payload = {"data": 999}  # corrupt
        # Should be treated as a miss and removed
        assert cache.get("ep", "u", False, 24, 1000) is None
        # Entry should have been evicted
        with cache._lock:
            assert key not in cache._store

    def test_payload_digest_computed_on_set(self):
        cache = AnalyticsCache(ttl_seconds=60.0)
        cache.set("ep", "u", False, 24, 1000, {"data": 42})
        with cache._lock:
            key = cache._key("ep", "u", False, 24, 1000)
            entry = cache._store[key]
            assert entry.payload_digest is not None
            assert entry.payload_digest.startswith("sha256:")
