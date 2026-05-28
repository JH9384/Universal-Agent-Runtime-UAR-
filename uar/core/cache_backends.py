"""Pluggable cache backends for UAR.

Supports file-based (default) and Redis backends with automatic fallback.
"""

import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, cast

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key generation (shared across backends)
# ---------------------------------------------------------------------------

_RELEVANT_KEYS = [
    "input_path",
    "file_hashes",
    "library_path",
    "model",
    "timeout",
    "graphrag_method",
    "ollama_model",
    "autonomi_network",
    "autonomi_public",
    "autonomi_address",
]


def _make_cache_key(skill_name: str, ctx: Dict[str, Any], goal: str) -> str:
    # Try full context first for correctness; fall back to relevant
    # keys if the full context contains non-serializable values.
    key_data = {
        "skill": skill_name,
        "goal": goal,
        "ctx": ctx,
        "execution_order": ctx.get("execution_order"),
    }
    try:
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode()).hexdigest()
    except (TypeError, ValueError):
        pass
    ctx_snapshot = {k: ctx.get(k) for k in _RELEVANT_KEYS}
    ctx_snapshot["execution_order"] = ctx.get("execution_order")
    key_data = {"skill": skill_name, "goal": goal}
    key_data.update({k: v for k, v in ctx_snapshot.items() if v is not None})
    try:
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    except (TypeError, ValueError):
        # Final fallback: deterministic hash of sorted stringified items.
        fallback = ":".join([skill_name, goal])
        try:
            item_hash = hash(frozenset((k, str(v)) for k, v in ctx.items()))
            fallback += ":" + str(item_hash)
        except Exception:
            logger.exception("Hash fallback failed")
        return hashlib.sha256(fallback.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class CacheBackend(ABC):
    """Abstract cache backend."""

    @abstractmethod
    def get(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> Optional[Any]:
        """Retrieve cached result."""
        raise NotImplementedError

    @abstractmethod
    def set(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        goal: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store result in cache."""
        raise NotImplementedError

    @abstractmethod
    def clear(self, skill_name: Optional[str] = None) -> None:
        """Remove entries."""
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return backend statistics."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# File backend (wraps existing ResultCache logic)
# ---------------------------------------------------------------------------


class FileCacheBackend(CacheBackend):
    """File-based cache with LRU eviction."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,
    ):
        self.cache_dir = cache_dir or os.path.expanduser("~/.uar_cache")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes
        self._lock = threading.Lock()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.cache")

    def get(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> Optional[Any]:
        key = _make_cache_key(skill_name, ctx, goal)
        path = self._cache_path(key)
        with self._lock:
            if not os.path.exists(path):
                return None
            age = time.time() - os.path.getmtime(path)
            if age > self.ttl_seconds:
                try:
                    os.remove(path)
                except OSError:
                    pass
                return None
            try:
                with open(path, "r") as f:
                    return json.load(f).get("result")
            except (
                json.JSONDecodeError,
                KeyError,
                IOError,
                UnicodeDecodeError,
            ):
                try:
                    os.remove(path)
                except OSError:
                    pass
                return None

    def set(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        goal: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            return
        key = _make_cache_key(skill_name, ctx, goal)
        path = self._cache_path(key)
        with self._lock:
            try:
                data = {
                    "result": result,
                    "timestamp": time.time(),
                    "skill": skill_name,
                }
                tmp = path + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(data, f)
                os.rename(tmp, path)
            except (IOError, TypeError):
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                return
            self._enforce_limits()

    def clear(self, skill_name: Optional[str] = None) -> None:
        with self._lock:
            if not os.path.exists(self.cache_dir):
                return
            for fname in os.listdir(self.cache_dir):
                if not fname.endswith(".cache"):
                    continue
                path = os.path.join(self.cache_dir, fname)
                if skill_name:
                    try:
                        with open(path, "r") as f:
                            if json.load(f).get("skill") == skill_name:
                                os.remove(path)
                    except (json.JSONDecodeError, IOError):
                        pass
                else:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.cache_dir):
                return {"total_entries": 0, "total_size_bytes": 0}
            total_entries = 0
            total_size = 0
            skill_counts: Dict[str, int] = {}
            for fname in os.listdir(self.cache_dir):
                if not fname.endswith(".cache"):
                    continue
                path = os.path.join(self.cache_dir, fname)
                try:
                    total_entries += 1
                    total_size += os.path.getsize(path)
                    with open(path, "r") as f:
                        skill = json.load(f).get("skill", "unknown")
                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
                except (json.JSONDecodeError, IOError):
                    pass
            return {
                "backend": "file",
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "skill_counts": skill_counts,
            }

    def _enforce_limits(self) -> None:
        if not os.path.exists(self.cache_dir):
            return
        files = []
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".cache"):
                path = os.path.join(self.cache_dir, fname)
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                    ts = data.get("timestamp", 0.0)
                    size = os.path.getsize(path)
                    files.append((path, ts, size))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    continue
        files.sort(key=lambda x: x[1])
        total_entries = len(files)
        total_size = sum(s for _, _, s in files)
        removed = 0
        removed_size = 0
        for path, _, size in files:
            if (
                total_entries - removed <= self.max_entries
                and total_size - removed_size <= self.max_size_bytes
            ):
                break
            try:
                os.remove(path)
                removed += 1
                removed_size += size
            except OSError:
                continue


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisCacheBackend(CacheBackend):
    """Redis-backed cache with optional TTL per entry."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 3600,
        key_prefix: str = "uar:cache:",
    ):
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self._lock = threading.Lock()
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._circuit_tripped = False

        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis as redis_lib

            self._client = (  # type: ignore[assignment]
                redis_lib.from_url(url or "", decode_responses=True)
            )
            self._client.ping()
            self._available = True
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s), falling back to no-op", exc
            )
            self._client = None  # type: ignore[assignment]
            self._available = False

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open/tripped.

        If open, bypasses Redis queries and returns True.
        """
        if not self._available:
            return True
        if self._circuit_tripped:
            now = time.time()
            if now - self._last_failure_time > 30.0:
                with self._lock:
                    self._circuit_tripped = False
                    self._failure_count = 0
                logger.info(
                    "Redis cache circuit breaker closed "
                    "(retrying connection)"
                )
                return False
            return True
        return False

    def _record_failure(self, exc: Exception) -> None:
        """Increment failure counter and trip the circuit breaker."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= 5:
                self._circuit_tripped = True
                logger.error(
                    "Redis cache circuit breaker TRIPPED after "
                    "5 consecutive failures. "
                    f"Bypassing Redis cache for 30s. Last error: {exc}"
                )

    def _record_success(self) -> None:
        """Reset failure counts on successful Redis operation."""
        if self._failure_count > 0:
            with self._lock:
                self._failure_count = 0
                self._circuit_tripped = False

    def _key(self, cache_key: str) -> str:
        return f"{self.key_prefix}{cache_key}"

    def get(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> Optional[Any]:
        if self._check_circuit_breaker():
            return None
        key = _make_cache_key(skill_name, ctx, goal)
        try:
            raw = self._client.get(self._key(key))  # type: ignore[union-attr]
            self._record_success()
            if raw is None:
                return None
            return json.loads(str(raw)).get("result")
        except Exception as exc:
            self._record_failure(exc)
            return None

    def set(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        goal: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        if self._check_circuit_breaker():
            return
        try:
            payload = json.dumps(
                {
                    "result": result,
                    "timestamp": time.time(),
                    "skill": skill_name,
                }
            )
        except (TypeError, ValueError):
            return
        key = _make_cache_key(skill_name, ctx, goal)
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        try:
            self._client.setex(self._key(key), ttl, payload)
            self._record_success()
        except Exception as exc:
            self._record_failure(exc)

    def clear(self, skill_name: Optional[str] = None) -> None:
        if self._check_circuit_breaker():
            return
        try:
            if skill_name:
                # Scan for keys matching prefix and filter by skill
                for k in self._client.scan_iter(match=f"{self.key_prefix}*"):
                    try:
                        raw = self._client.get(k)
                        if raw:
                            data = json.loads(str(raw))
                            if data.get("skill") == skill_name:
                                self._client.delete(k)
                    except Exception:
                        logger.exception("Redis key delete failed")
            else:
                for k in self._client.scan_iter(match=f"{self.key_prefix}*"):
                    self._client.delete(k)
            self._record_success()
        except Exception as exc:
            self._record_failure(exc)

    def get_stats(self) -> Dict[str, Any]:
        if self._check_circuit_breaker():
            return {
                "backend": "redis",
                "available": False,
                "circuit_tripped": self._circuit_tripped,
            }
        try:
            info = cast(dict, self._client.info("keyspace"))
            total_keys = sum(
                v.get("keys", 0)
                for v in info.values()
                if isinstance(v, dict)
            )
            self._record_success()
            return {
                "backend": "redis",
                "available": True,
                "total_keys_estimate": total_keys,
                "prefix": self.key_prefix,
            }
        except Exception as exc:
            self._record_failure(exc)
            return {
                "backend": "redis",
                "available": False,
                "circuit_tripped": self._circuit_tripped,
            }


# ---------------------------------------------------------------------------
# Auto-selecting backend
# ---------------------------------------------------------------------------


class AutoCacheBackend(CacheBackend):
    """Uses Redis if available and configured, otherwise file."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,
        redis_url: Optional[str] = None,
        key_prefix: str = "uar:cache:",
    ):
        self._file = FileCacheBackend(
            cache_dir=cache_dir,
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
            max_size_bytes=max_size_bytes,
        )
        self._redis: Optional[RedisCacheBackend] = None
        if os.getenv("UAR_CACHE_BACKEND", "").lower() == "redis":
            self._redis = RedisCacheBackend(
                redis_url=redis_url,
                ttl_seconds=ttl_seconds,
                key_prefix=key_prefix,
            )
            if not self._redis._available:
                logger.warning(
                    "Redis requested but unavailable, using file backend"
                )
                self._redis = None

    @property
    def cache_dir(self) -> str:
        return self._file.cache_dir

    def _backend(self) -> CacheBackend:
        return self._redis if self._redis is not None else self._file

    def get(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> Optional[Any]:
        return self._backend().get(skill_name, ctx, goal)

    def set(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        goal: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self._backend().set(skill_name, ctx, goal, result, ttl_seconds)

    def clear(self, skill_name: Optional[str] = None) -> None:
        self._file.clear(skill_name)
        if self._redis:
            self._redis.clear(skill_name)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_backend": ("redis" if self._redis is not None else "file"),
            "file_stats": self._file.get_stats(),
            "redis_stats": (self._redis.get_stats() if self._redis else None),
        }
