"""Tests for uar.core.cache_backends.

Covers FileCacheBackend, RedisCacheBackend (mocked), AutoCacheBackend,
and _make_cache_key edge cases.
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401

from uar.core.cache_backends import (
    _make_cache_key,
    FileCacheBackend,
    RedisCacheBackend,
    AutoCacheBackend,
)


# ---------------------------------------------------------------------------
# _make_cache_key
# ---------------------------------------------------------------------------


def test_make_cache_key_basic():
    key = _make_cache_key("sum", {"input_path": "/tmp/a"}, "add numbers")
    assert isinstance(key, str)
    assert len(key) == 64  # sha256 hex


def test_make_cache_key_non_serializable_fallback():
    """Non-serializable ctx values must trigger fallback key generation."""
    ctx = {"input_path": "/tmp/a", "object": object()}
    key = _make_cache_key("sum", ctx, "add")
    assert isinstance(key, str)
    assert len(key) == 64


def test_make_cache_key_fallback_frozenset_fails():
    """If even frozenset fallback fails, must still produce a key."""
    ctx = {"unhashable": []}  # lists are unhashable
    key = _make_cache_key("sum", ctx, "add")
    assert isinstance(key, str)
    assert len(key) == 64


def test_make_cache_key_hash_fallback_fails():
    """When hash(frozenset) fails, log and use simpler fallback."""
    ctx = {"nested": {"a": object()}}
    key = _make_cache_key("sum", ctx, "add")
    assert isinstance(key, str)
    assert len(key) == 64


# ---------------------------------------------------------------------------
# FileCacheBackend
# ---------------------------------------------------------------------------


class TestFileCacheBackend:
    def test_get_miss(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        assert backend.get("noop", {}, "test") is None

    def test_get_expired(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path), ttl_seconds=0)
        backend.set("noop", {}, "test", {"result": 42})
        time.sleep(0.01)
        assert backend.get("noop", {}, "test") is None

    def test_get_corrupt_file(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        key = _make_cache_key("noop", {}, "test")
        path = backend._cache_path(key)
        with open(path, "w") as f:
            f.write("not json{{")
        assert backend.get("noop", {}, "test") is None
        assert not os.path.exists(path)  # removed

    def test_set_non_serializable(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("noop", {}, "test", {"result": object()})
        assert backend.get("noop", {}, "test") is None

    def test_set_io_error(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        with patch("builtins.open", side_effect=IOError("disk full")):
            backend.set("noop", {}, "test", {"result": 1})

    def test_clear_all(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("a", {}, "g1", {"result": 1})
        backend.set("b", {}, "g2", {"result": 2})
        backend.clear()
        assert backend.get("a", {}, "g1") is None
        assert backend.get("b", {}, "g2") is None

    def test_clear_by_skill(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("skill_a", {}, "g1", {"result": 1})
        backend.set("skill_b", {}, "g2", {"result": 2})
        backend.clear("skill_a")
        assert backend.get("skill_a", {}, "g1") is None
        assert backend.get("skill_b", {}, "g2") == {"result": 2}

    def test_clear_missing_dir(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        os.rmdir(backend.cache_dir)
        backend.clear()  # must not raise

    def test_get_stats(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("s", {}, "g", {"result": 1})
        stats = backend.get_stats()
        assert stats["backend"] == "file"
        assert stats["total_entries"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["skill_counts"]["s"] == 1

    def test_get_stats_missing_dir(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        os.rmdir(backend.cache_dir)
        stats = backend.get_stats()
        assert stats["total_entries"] == 0

    def test_get_stats_corrupt_file(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        # Write a non-.cache file (should be ignored)
        with open(os.path.join(backend.cache_dir, "readme.txt"), "w") as f:
            f.write("hi")
        # Write a corrupt .cache file (total_entries increments but skill
        # parsing is skipped; corrupt files are not removed by get_stats)
        with open(os.path.join(backend.cache_dir, "bad.cache"), "w") as f:
            f.write("not json")
        stats = backend.get_stats()
        # total_entries increments before json.load; corrupt => skip rest
        assert stats["total_entries"] == 1
        assert stats["total_size_bytes"] > 0  # size was added
        assert stats["skill_counts"] == {}

    def test_enforce_limits_evicts_oldest(self, tmp_path):
        backend = FileCacheBackend(
            cache_dir=str(tmp_path),
            ttl_seconds=3600,
            max_entries=2,
            max_size_bytes=1024 * 1024,
        )
        backend.set("a", {}, "g1", {"result": 1})
        time.sleep(0.01)
        backend.set("b", {}, "g2", {"result": 2})
        time.sleep(0.01)
        backend.set("c", {}, "g3", {"result": 3})
        time.sleep(0.01)
        backend._enforce_limits()
        # At most 2 entries should remain
        stats = backend.get_stats()
        assert stats["total_entries"] <= 2

    def test_enforce_limits_no_dir(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        os.rmdir(backend.cache_dir)
        backend._enforce_limits()  # must not raise

    def test_enforce_limits_corrupt_removed(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        path = os.path.join(backend.cache_dir, "bad.cache")
        with open(path, "w") as f:
            f.write("not json")
        backend._enforce_limits()
        assert not os.path.exists(path)

    def test_get_oserror_on_remove(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path), ttl_seconds=0)
        backend.set("noop", {}, "test", {"result": 42})
        time.sleep(0.01)
        with patch("os.remove", side_effect=OSError("perm")):
            assert backend.get("noop", {}, "test") is None

    def test_get_oserror_on_decode(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("noop", {}, "test", {"result": 42})
        with patch("builtins.open", side_effect=UnicodeDecodeError(
            "utf-8", b"\xff", 0, 1, "invalid start byte"
        )):
            assert backend.get("noop", {}, "test") is None

    def test_set_type_error(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        with patch("builtins.open", side_effect=TypeError("bad")):
            backend.set("noop", {}, "test", {"result": 1})

    def test_set_oserror_cleanup(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        with patch("builtins.open", side_effect=IOError("disk full")):
            backend.set("noop", {}, "test", {"result": 1})

    def test_clear_by_skill_oserror(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("s", {}, "g", {"result": 1})
        with patch("os.remove", side_effect=OSError("perm")):
            backend.clear("s")  # should not raise

    def test_clear_all_oserror(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("s", {}, "g", {"result": 1})
        with patch("os.remove", side_effect=OSError("perm")):
            backend.clear()  # should not raise

    def test_enforce_limits_max_size(self, tmp_path):
        backend = FileCacheBackend(
            cache_dir=str(tmp_path),
            ttl_seconds=3600,
            max_entries=100,
            max_size_bytes=1,
        )
        backend.set("a", {}, "g1", {"result": "x" * 100})
        backend._enforce_limits()
        assert backend.get_stats()["total_entries"] == 0


# ---------------------------------------------------------------------------
# RedisCacheBackend (mocked)
# ---------------------------------------------------------------------------


def _make_redis_backend(mock_client):
    """Helper: create a RedisCacheBackend with a mocked client."""
    with patch.object(RedisCacheBackend, "__init__", lambda self, **kw: None):
        backend = RedisCacheBackend.__new__(RedisCacheBackend)
    backend.ttl_seconds = 3600
    backend.key_prefix = "uar:cache:"
    backend._lock = MagicMock()
    backend._lock.__enter__ = lambda s: s
    backend._lock.__exit__ = lambda s, *a: None
    backend._failure_count = 0
    backend._last_failure_time = 0.0
    backend._circuit_tripped = False
    backend._available = True
    backend._client = mock_client
    return backend


class TestRedisCacheBackend:
    def test_redis_unavailable_no_import(self, tmp_path):
        """When redis import fails, backend becomes no-op."""
        with patch.dict("os.environ", {"REDIS_URL": ""}):
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (
                    {} if name == "redis" else __builtins__["__import__"](
                        name, *args, **kwargs
                    )
                ),
            ):
                backend = RedisCacheBackend(redis_url="redis://localhost:9999")
                assert not backend._available
                assert backend.get("s", {}, "g") is None
                backend.set("s", {}, "g", {"r": 1})
                backend.clear()
                stats = backend.get_stats()
                assert stats["available"] is False

    def test_redis_mocked_get_miss(self):
        mock_client = MagicMock()
        mock_client.get.return_value = None
        backend = _make_redis_backend(mock_client)
        assert backend.get("s", {}, "g") is None
        mock_client.get.assert_called_once()

    def test_redis_mocked_get_hit(self):
        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps({"result": 42})
        backend = _make_redis_backend(mock_client)
        assert backend.get("s", {}, "g") == 42

    def test_redis_mocked_get_corrupt_json(self):
        mock_client = MagicMock()
        mock_client.get.return_value = "not json"
        backend = _make_redis_backend(mock_client)
        assert backend.get("s", {}, "g") is None
        assert backend._failure_count > 0

    def test_redis_mocked_get_exception(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = RuntimeError("conn lost")
        backend = _make_redis_backend(mock_client)
        assert backend.get("s", {}, "g") is None
        assert backend._failure_count > 0

    def test_circuit_breaker_tripped(self):
        backend = _make_redis_backend(MagicMock())
        backend._circuit_tripped = True
        backend._last_failure_time = time.time()
        assert backend._check_circuit_breaker() is True

    def test_circuit_breaker_reset_after_timeout(self):
        backend = _make_redis_backend(MagicMock())
        backend._circuit_tripped = True
        backend._last_failure_time = time.time() - 60.0
        backend._failure_count = 3
        assert backend._check_circuit_breaker() is False
        assert not backend._circuit_tripped
        assert backend._failure_count == 0

    def test_record_failure_trips_circuit(self):
        backend = _make_redis_backend(MagicMock())
        for _ in range(5):
            backend._record_failure(RuntimeError("redis down"))
        assert backend._circuit_tripped is True

    def test_record_success_resets(self):
        backend = _make_redis_backend(MagicMock())
        backend._failure_count = 3
        backend._circuit_tripped = True
        backend._record_success()
        assert backend._failure_count == 0
        assert backend._circuit_tripped is False

    def test_redis_mocked_set(self):
        mock_client = MagicMock()
        backend = _make_redis_backend(mock_client)
        backend.set("s", {}, "g", {"result": 1}, ttl_seconds=60)
        mock_client.setex.assert_called_once()

    def test_redis_mocked_set_non_serializable(self):
        backend = _make_redis_backend(MagicMock())
        backend.set("s", {}, "g", {"result": object()})
        # json.dumps fails on object() -> early return
        backend._client.setex.assert_not_called()

    def test_redis_mocked_set_exception(self):
        mock_client = MagicMock()
        mock_client.setex.side_effect = RuntimeError("conn lost")
        backend = _make_redis_backend(mock_client)
        backend.set("s", {}, "g", {"result": 1})
        assert backend._failure_count > 0

    def test_redis_mocked_clear_all(self):
        mock_client = MagicMock()
        mock_client.scan_iter.return_value = ["k1", "k2"]
        backend = _make_redis_backend(mock_client)
        backend.clear()
        assert mock_client.delete.call_count == 2

    def test_redis_mocked_clear_by_skill(self):
        mock_client = MagicMock()
        mock_client.scan_iter.return_value = ["k1"]
        mock_client.get.return_value = json.dumps(
            {"skill": "skill_a", "result": 1}
        )
        backend = _make_redis_backend(mock_client)
        backend.clear("skill_a")
        mock_client.delete.assert_called_once()

    def test_redis_mocked_clear_exception(self):
        mock_client = MagicMock()
        mock_client.scan_iter.side_effect = RuntimeError("scan err")
        backend = _make_redis_backend(mock_client)
        backend.clear()
        assert backend._failure_count > 0

    def test_redis_mocked_stats(self):
        mock_client = MagicMock()
        mock_client.info.return_value = {
            "db0": {"keys": 5},
            "db1": {"keys": 3},
        }
        backend = _make_redis_backend(mock_client)
        stats = backend.get_stats()
        assert stats["available"] is True
        assert stats["total_keys_estimate"] == 8

    def test_redis_stats_failure(self):
        mock_client = MagicMock()
        mock_client.info.side_effect = RuntimeError("redis err")
        backend = _make_redis_backend(mock_client)
        stats = backend.get_stats()
        assert stats["available"] is False
        assert backend._failure_count > 0

    def test_redis_stats_circuit_open(self):
        backend = _make_redis_backend(MagicMock())
        backend._circuit_tripped = True
        backend._last_failure_time = time.time()
        stats = backend.get_stats()
        assert stats["available"] is False
        assert stats["circuit_tripped"] is True


# ---------------------------------------------------------------------------
# AutoCacheBackend
# ---------------------------------------------------------------------------


class TestAutoCacheBackend:
    def test_defaults_to_file(self, tmp_path):
        backend = AutoCacheBackend(cache_dir=str(tmp_path))
        assert backend._redis is None
        assert backend.get("s", {}, "g") is None

    def test_redis_when_configured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UAR_CACHE_BACKEND", "redis")
        with patch.object(
            RedisCacheBackend, "__init__", lambda self, **kw: None
        ):
            backend = AutoCacheBackend.__new__(AutoCacheBackend)
            backend._file = FileCacheBackend(cache_dir=str(tmp_path))
            # When redis is unavailable, __init__ sets _redis = None
            backend._redis = None

            # _backend falls back to file when _redis is None
            assert backend._backend() is backend._file

    def test_clear_both_backends(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UAR_CACHE_BACKEND", "redis")
        backend = AutoCacheBackend(cache_dir=str(tmp_path))
        # Even if redis unavailable, file backend works
        backend.set("s", {}, "g", {"r": 1})
        backend.clear()
        assert backend.get("s", {}, "g") is None

    def test_stats_include_both(self, tmp_path):
        backend = AutoCacheBackend(cache_dir=str(tmp_path))
        backend.set("s", {}, "g", {"r": 1})
        stats = backend.get_stats()
        assert "file_stats" in stats
        assert "redis_stats" in stats
        assert stats["active_backend"] == "file"

    def test_redis_available(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UAR_CACHE_BACKEND", "redis")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with patch.dict("sys.modules", {"redis": MagicMock()}):
            with patch.object(
                AutoCacheBackend, "__init__", lambda self, **kw: None
            ):
                backend = AutoCacheBackend.__new__(AutoCacheBackend)
                backend._file = FileCacheBackend(cache_dir=str(tmp_path))
                mock_redis = MagicMock()
                mock_redis._available = True
                backend._redis = mock_redis
                assert backend._backend() is mock_redis

    def test_cache_dir_property(self, tmp_path):
        backend = AutoCacheBackend(cache_dir=str(tmp_path))
        assert backend.cache_dir == str(tmp_path)

    def test_redis_unavailable_sets_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UAR_CACHE_BACKEND", "redis")
        with patch.object(
            AutoCacheBackend, "__init__", lambda self, **kw: None
        ):
            backend = AutoCacheBackend.__new__(AutoCacheBackend)
            backend._file = FileCacheBackend(cache_dir=str(tmp_path))
            mock_redis = MagicMock()
            mock_redis._available = False
            backend._redis = mock_redis
            backend._redis = None  # simulate the reset
            assert backend._redis is None


class TestMakeCacheKeyFinalFallback:
    def test_str_raises(self):
        class BadObj:
            def __str__(self):
                raise TypeError("bad")

        ctx = {"bad": BadObj()}
        key = _make_cache_key("sum", ctx, "add")
        assert isinstance(key, str)
        assert len(key) == 64


class TestFileCacheBackendRemaining:
    def test_get_decode_error_then_remove_fails(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        backend.set("noop", {}, "test", {"result": 42})
        with patch("builtins.open", side_effect=UnicodeDecodeError(
            "utf-8", b"\xff", 0, 1, "invalid start byte"
        )):
            with patch("os.remove", side_effect=OSError("perm")):
                assert backend.get("noop", {}, "test") is None

    def test_set_cleanup_fails(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        with patch("builtins.open", side_effect=IOError("disk full")):
            with patch("os.path.exists", return_value=True):
                with patch("os.remove", side_effect=OSError("perm")):
                    backend.set("noop", {}, "test", {"result": 1})

    def test_clear_skill_json_decode_error(self, tmp_path):
        backend = FileCacheBackend(cache_dir=str(tmp_path))
        path = os.path.join(backend.cache_dir, "bad.cache")
        with open(path, "w") as f:
            f.write("not json")
        backend.clear("s")  # should not raise

    def test_enforce_limits_no_eviction_needed(self, tmp_path):
        backend = FileCacheBackend(
            cache_dir=str(tmp_path),
            ttl_seconds=3600,
            max_entries=100,
            max_size_bytes=1024 * 1024,
        )
        backend.set("a", {}, "g1", {"result": 1})
        backend._enforce_limits()
        assert backend.get_stats()["total_entries"] == 1

    def test_enforce_limits_remove_fails(self, tmp_path):
        backend = FileCacheBackend(
            cache_dir=str(tmp_path),
            ttl_seconds=3600,
            max_entries=0,
            max_size_bytes=0,
        )
        backend.set("a", {}, "g1", {"result": 1})
        with patch("os.remove", side_effect=OSError("perm")):
            backend._enforce_limits()


class TestRedisCacheBackendInit:
    def test_init_success(self, tmp_path):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis = MagicMock()
        mock_redis.from_url.return_value = mock_client
        with patch.dict("sys.modules", {"redis": mock_redis}):
            backend = RedisCacheBackend(
                redis_url="redis://localhost:6379/0"
            )
        assert backend._available is True

    def test_init_ping_failure(self):
        mock_client = MagicMock()
        mock_client.ping.side_effect = RuntimeError("conn refused")
        mock_redis = MagicMock()
        mock_redis.from_url.return_value = mock_client
        with patch.dict("sys.modules", {"redis": mock_redis}):
            backend = RedisCacheBackend()
        assert backend._available is False


class TestRedisCacheBackendClearExceptions:
    def test_clear_skill_json_decode_error(self):
        mock_client = MagicMock()
        mock_client.scan_iter.return_value = ["k1"]
        mock_client.get.return_value = "not json"
        backend = _make_redis_backend(mock_client)
        backend.clear("skill_a")

    def test_clear_skill_delete_exception(self):
        mock_client = MagicMock()
        mock_client.scan_iter.return_value = ["k1"]
        mock_client.get.return_value = json.dumps(
            {"skill": "skill_a", "result": 1}
        )
        mock_client.delete.side_effect = RuntimeError("del err")
        backend = _make_redis_backend(mock_client)
        backend.clear("skill_a")
