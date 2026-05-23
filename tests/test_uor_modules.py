"""Unit tests for UOR ecosystem modules.

Covers: secure_keys, object_cache, rate_limiting, rdf_formats.
"""

from __future__ import annotations

import time

import pytest

from uar.uor.secure_keys import SecureKeyStore, KeyManager
from uar.uor.object_cache import UORObjectCache, CachedObjectAccessor
from uar.uor.rate_limiting import (
    RateLimiter,
    SlidingWindowRateLimiter,
    UORAPIClient,
)
from uar.uor import rdf_formats


# ---------------------------------------------------------------------------
# secure_keys
# ---------------------------------------------------------------------------

class TestSecureKeyStore:
    def test_store_and_retrieve(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        store.store_key("mykey", "secretvalue")
        assert store.retrieve_key("mykey") == "secretvalue"
        store.delete_key("mykey")

    def test_retrieve_missing(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        assert store.retrieve_key("nonexistent") is None

    def test_delete_missing(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        assert store.delete_key("nonexistent") is False

    def test_list_keys(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        store.store_key("alpha", "a")
        store.store_key("beta", "b")
        keys = store.list_keys()
        assert "alpha" in keys
        assert "beta" in keys
        store.delete_key("alpha")
        store.delete_key("beta")

    def test_prefix_isolation(self):
        store_a = SecureKeyStore(prefix="A_")
        store_b = SecureKeyStore(prefix="B_")
        store_a.store_key("same", "val_a")
        store_b.store_key("same", "val_b")
        assert store_a.retrieve_key("same") == "val_a"
        assert store_b.retrieve_key("same") == "val_b"
        store_a.delete_key("same")
        store_b.delete_key("same")


class TestKeyManager:
    def test_generate_key_pair_missing_cryptography(self):
        try:
            import cryptography  # noqa: F401

            pytest.skip("cryptography is installed")
        except ImportError:
            pass
        mgr = KeyManager()
        with pytest.raises(NotImplementedError) as exc:
            mgr.generate_key_pair("test_id")
        assert "cryptography library required" in str(exc.value)

    def test_sign_and_verify_missing_cryptography(self):
        try:
            import cryptography  # noqa: F401

            pytest.skip("cryptography is installed")
        except ImportError:
            pass
        mgr = KeyManager()
        assert mgr.sign_data("test", b"hello") is None
        assert mgr.verify_signature("test", b"hello", "sig") is False


# ---------------------------------------------------------------------------
# object_cache
# ---------------------------------------------------------------------------

class TestUORObjectCache:
    def test_basic_get_set(self):
        cache = UORObjectCache(max_size=2)
        cache.set("a", 1)
        assert cache.get("a") == 1

    def test_missing_returns_none(self):
        cache = UORObjectCache()
        assert cache.get("missing") is None
        stats = cache.get_stats()
        assert stats["misses"] == 1

    def test_hit_increments(self):
        cache = UORObjectCache()
        cache.set("x", 10)
        cache.get("x")
        cache.get("x")
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 0

    def test_lru_eviction(self):
        cache = UORObjectCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None  # evicted
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_delete(self):
        cache = UORObjectCache()
        cache.set("k", "v")
        assert cache.delete("k") is True
        assert cache.get("k") is None
        assert cache.delete("k") is False

    def test_clear(self):
        cache = UORObjectCache()
        cache.set("a", 1)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get_stats()["size"] == 0

    def test_ttl_expiration(self):
        cache = UORObjectCache()
        cache.set("k", "v", ttl=0.01)
        assert cache.get("k") == "v"
        time.sleep(0.02)
        assert cache.get("k") is None

    def test_cleanup_expired(self):
        cache = UORObjectCache()
        cache.set("a", 1, ttl=0.01)
        cache.set("b", 2, ttl=10)
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_get_keys(self):
        cache = UORObjectCache()
        cache.set("x", 1)
        cache.set("y", 2)
        assert sorted(cache.get_keys()) == ["x", "y"]

    def test_stats_hit_rate(self):
        cache = UORObjectCache()
        assert cache.get_stats()["hit_rate"] == 0.0
        cache.set("a", 1)
        cache.get("a")
        stats = cache.get_stats()
        assert stats["hit_rate"] == 1.0


class TestCachedObjectAccessor:
    def test_fetch_and_cache(self):
        def fetch(key):
            return {"data": key}

        accessor = CachedObjectAccessor(fetch)
        result = accessor.get("obj1")
        assert result == {"data": "obj1"}
        # Second call should use cache
        result2 = accessor.get("obj1")
        assert result2 == {"data": "obj1"}

    def test_prefetch(self):
        def fetch(key):
            return f"value-{key}"

        accessor = CachedObjectAccessor(fetch)
        accessor.prefetch(["a", "b"])
        assert accessor.get("a") == "value-a"
        assert accessor.get("b") == "value-b"

    def test_invalidate(self):
        def fetch(key):
            return key.upper()

        accessor = CachedObjectAccessor(fetch)
        accessor.get("x")
        accessor.invalidate("x")
        assert accessor.cache.get("x") is None


# ---------------------------------------------------------------------------
# rate_limiting
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allow_under_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        info = rl.is_allowed("client1")
        assert info.allowed is True
        assert info.remaining == 2

    def test_block_over_limit(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("client1")
        rl.is_allowed("client1")
        info = rl.is_allowed("client1")
        assert info.allowed is False
        assert info.remaining == 0

    def test_reset(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("client1")
        rl.is_allowed("client1")
        rl.reset("client1")
        info = rl.is_allowed("client1")
        assert info.allowed is True

    def test_stats(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed("c")
        stats = rl.get_stats("c")
        assert stats["current_requests"] == 1
        assert stats["remaining"] == 4

    def test_window_expiration(self):
        rl = RateLimiter(max_requests=1, window_seconds=0.05)
        rl.is_allowed("c")
        time.sleep(0.06)
        info = rl.is_allowed("c")
        assert info.allowed is True


class TestSlidingWindowRateLimiter:
    def test_basic_allow(self):
        rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert rl.is_allowed("c").allowed is True
        assert rl.is_allowed("c").allowed is True
        assert rl.is_allowed("c").allowed is False


class TestUORAPIClient:
    def test_rate_limit_check(self):
        client = UORAPIClient(
            "http://example.com", rate_limiter=RateLimiter(max_requests=1)
        )
        info = client.check_rate_limit("key1")
        assert info.allowed is True
        info2 = client.check_rate_limit("key1")
        assert info2.allowed is False

    def test_get_object_rate_limited(self):
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        client = UORAPIClient("http://example.com", rate_limiter=limiter)
        assert client.get_object("digest1") is None

    def test_put_object_rate_limited(self):
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        client = UORAPIClient("http://example.com", rate_limiter=limiter)
        assert client.put_object({"key": "val"}) is None


# ---------------------------------------------------------------------------
# rdf_formats
# ---------------------------------------------------------------------------

class TestRDFConverter:
    def test_missing_rdflib(self):
        if rdf_formats.RDFLIB_AVAILABLE:
            pytest.skip("rdflib is installed")
        conv = rdf_formats.RDFConverter()
        result = conv.jsonld_to_rdf('{"@context": {}}')
        assert result.success is False
        assert "rdflib not available" in result.error

    def test_converter_init(self):
        conv = rdf_formats.RDFConverter(base_uri="http://test/")
        assert conv.base_uri == "http://test/"


class TestOWLConverter:
    def test_missing_rdflib(self):
        if rdf_formats.RDFLIB_AVAILABLE:
            pytest.skip("rdflib is installed")
        conv = rdf_formats.OWLConverter()
        result = conv.schema_to_owl({"title": "Test"})
        assert result.success is False
        assert "rdflib not available" in result.error

    def test_converter_init(self):
        conv = rdf_formats.OWLConverter(base_uri="http://test/")
        assert conv.base_uri == "http://test/"


class TestRDFConversionResult:
    def test_to_dict(self):
        result = rdf_formats.RDFConversionResult(
            success=True, data="test", format="json-ld"
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == "test"
        assert d["format"] == "json-ld"
        assert d["error"] is None
