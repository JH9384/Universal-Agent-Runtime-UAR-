"""Per-skill result cache with SHA-256 keyed storage.

Wraps any skill function to cache its result keyed by:
- skill name
- serialized goal metadata
- a configurable TTL

Usage:
    from uar.core.skill_cache import cached_skill

    @cached_skill(ttl_seconds=300)
    @register_skill("math_compute")
    def math_compute(ctx):
        ...
"""

import atexit
import functools
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# Compression: prefer zstd (faster), fallback to zlib
try:
    import zstandard as zstd
    _HAS_ZSTD = True
except ImportError:
    import zlib
    _HAS_ZSTD = False

logger = logging.getLogger(__name__)

# Optional Redis connection for cross-worker skill caching
_redis_client: Any = None  # type: ignore[name-defined]


def _get_redis():
    """Lazy Redis connection for skill cache."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis

        _redis_client = redis.from_url(redis_url, decode_responses=True)
        return _redis_client
    except Exception:  # noqa: BLE001
        return None


def _close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            logger.exception("Redis client close failed")
        _redis_client = None


atexit.register(_close_redis)


class SkillCache:
    """In-memory LRU cache for skill results.

    Thread-safe.  Results are keyed by SHA-256 of the serialized
    (skill_name, metadata) tuple.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._order: Dict[str, None] = {}  # OrderedDict for O(1) LRU

    def _make_key(self, skill_name: str, metadata: Dict[str, Any]) -> str:
        """Deterministic fast key from skill + metadata (blake2b)."""
        payload = json.dumps(
            {"skill": skill_name, "metadata": metadata},
            sort_keys=True,
            default=str,
        )
        return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()

    def get(
        self, skill_name: str, metadata: Dict[str, Any]
    ) -> Optional[Any]:
        """Return cached result or ``None`` if expired / missing."""
        key = self._make_key(skill_name, metadata)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry["expires"] < time.time():
                self._store.pop(key, None)
                self._order.pop(key, None)
                return None
            # Touch for LRU
            self._order.pop(key, None)
            self._order[key] = None
            logger.debug(
                "Cache hit: %s (%s...)", skill_name, key[:8]
            )
            return entry["value"]

    def set(
        self,
        skill_name: str,
        metadata: Dict[str, Any],
        value: Any,
        ttl_seconds: float,
    ) -> None:
        """Store a result with the given TTL."""
        key = self._make_key(skill_name, metadata)
        with self._lock:
            # O(1) LRU eviction: drop oldest entries when over maxsize
            while len(self._store) >= self._maxsize:
                oldest = next(iter(self._order))
                self._order.pop(oldest, None)
                self._store.pop(oldest, None)

            self._store[key] = {
                "value": value,
                "expires": time.time() + ttl_seconds,
                "skill": skill_name,
            }
            self._order.pop(key, None)
            self._order[key] = None
            logger.debug(
                "Cache set: %s (%s...)", skill_name, key[:8]
            )

    def invalidate(
        self, skill_name: Optional[str] = None
    ) -> int:
        """Remove entries. If skill_name given, only remove for that skill."""
        with self._lock:
            if skill_name is None:
                count = len(self._store)
                self._store.clear()
                self._order.clear()
                return count
            to_remove = [
                k for k, v in self._store.items() if v["skill"] == skill_name
            ]
            for k in to_remove:
                self._store.pop(k, None)
                self._order.pop(k, None)
            return len(to_remove)

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            return {
                "size": len(self._store),
                "maxsize": self._maxsize,
                "skills": sorted({v["skill"] for v in self._store.values()}),
            }


class RedisSkillCache:
    """Redis-backed skill cache for cross-worker result sharing.

    Uses the same SHA-256 key scheme as :class:`SkillCache` so that
    hits are valid regardless of which worker stored the entry.
    """

    _REDIS_PREFIX = "uar:skill_cache:"

    def __init__(self, maxsize: int = 1024) -> None:
        self._maxsize = maxsize
        self._r = _get_redis()
        if self._r is None:
            raise RuntimeError(
                "RedisSkillCache requires REDIS_URL to be set"
            )

    def _make_key(self, skill_name: str, metadata: Dict[str, Any]) -> str:
        """Deterministic SHA-256 key from skill + metadata."""
        payload = json.dumps(
            {"skill": skill_name, "metadata": metadata},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _redis_key(self, key: str) -> str:
        return f"{self._REDIS_PREFIX}{key}"

    def get(
        self, skill_name: str, metadata: Dict[str, Any]
    ) -> Optional[Any]:
        """Return cached result from Redis or ``None``."""
        key = self._make_key(skill_name, metadata)
        # Bloom filter: skip Redis lookup if key definitely absent
        if _bloom_filter and not _bloom_filter.might_contain(key):
            return None
        try:
            # Try zstd compressed key first
            raw = self._r.get(self._redis_key(key) + ":z")
            if raw is not None:
                if _HAS_ZSTD:
                    return json.loads(zstd.ZstdDecompressor().decompress(raw))
                return json.loads(zlib.decompress(raw))
            raw = self._r.get(self._redis_key(key))
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupted cache entry for key %s", key)
            return None
        except Exception:
            logger.warning("Redis cache get failed, treating as miss")
            return None

    def set(
        self,
        skill_name: str,
        metadata: Dict[str, Any],
        value: Any,
        ttl_seconds: float,
    ) -> None:
        """Store a serialized result in Redis with TTL.

        Optional zstd compression (UAR_CACHE_COMPRESS=true)
        for large skill results. Updates bloom filter on set.
        """
        key = self._redis_key(self._make_key(skill_name, metadata))
        try:
            payload = json.dumps(value, default=str).encode("utf-8")
            if os.getenv("UAR_CACHE_COMPRESS", "true").lower() == "true":
                if _HAS_ZSTD:
                    payload = zstd.ZstdCompressor(level=3).compress(payload)
                else:
                    payload = zlib.compress(payload, level=3)
                key += ":z"
            self._r.setex(key, int(ttl_seconds), payload)
            if _bloom_filter:
                _bloom_filter.add(self._make_key(skill_name, metadata))
            logger.debug("Redis cache set: %s", skill_name)
        except Exception:
            logger.exception("Redis cache set failed")

    def invalidate(self, skill_name: Optional[str] = None) -> int:
        """Remove entries from Redis.

        Uses prefix-based scan for skill-specific invalidation.
        """
        try:
            if skill_name is None:
                keys = self._r.keys(f"{self._REDIS_PREFIX}*")
                if keys:
                    self._r.delete(*keys)
                return len(keys) if keys else 0
            # Prefix scan: key pattern includes skill name hash prefix
            # We scan all keys and filter by embedded skill metadata
            keys = self._r.keys(f"{self._REDIS_PREFIX}*")
            removed = 0
            for key in keys or []:
                raw = self._r.get(key)
                if raw is None:
                    continue
                try:
                    if key.endswith(":z"):
                        raw = zlib.decompress(raw)
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    entry = json.loads(raw)
                    if isinstance(entry, dict) and entry.get(
                        "skill"
                    ) == skill_name:
                        self._r.delete(key)
                        removed += 1
                except Exception:
                    logger.exception("Redis key delete failed")
            return removed
        except Exception:
            logger.warning("Redis cache invalidate failed")
            return 0

    def stats(self) -> Dict[str, Any]:
        """Return approximate cache statistics from Redis."""
        try:
            keys = self._r.keys(f"{self._REDIS_PREFIX}*")
            return {
                "size": len(keys) if keys else 0,
                "maxsize": self._maxsize,
                "skills": "unknown (Redis scan)",
            }
        except Exception:
            logger.warning("Redis cache stats failed")
            return {"size": 0, "maxsize": self._maxsize, "skills": []}


# Global shared cache instance
_global_skill_cache: Optional[Any] = None
_global_cache_lock = threading.Lock()


class _BloomFilter:
    """Simple bit-array bloom filter for cache key presence.

    Uses a single 64KB bit array (~500K entries at 1% false positive).
    """

    def __init__(self, size: int = 524_288, hash_count: int = 4) -> None:
        self.size = size
        self.hash_count = hash_count
        self.bits = bytearray(size // 8)

    def add(self, item: str) -> None:
        for i in range(self.hash_count):
            idx = hash((item, i)) % self.size
            byte_idx = idx // 8
            bit_idx = idx % 8
            self.bits[byte_idx] |= 1 << bit_idx

    def might_contain(self, item: str) -> bool:
        for i in range(self.hash_count):
            idx = hash((item, i)) % self.size
            byte_idx = idx // 8
            bit_idx = idx % 8
            if not (self.bits[byte_idx] & (1 << bit_idx)):
                return False
        return True


# Optional bloom filter to skip Redis lookups for known-absent keys
_bloom_filter: Optional[_BloomFilter] = None
if os.getenv("UAR_CACHE_BLOOM", "true").lower() == "true":
    _bloom_filter = _BloomFilter()


def get_skill_cache(maxsize: int = 1024) -> Any:
    """Get or create the global skill cache.

    Returns :class:`RedisSkillCache` if ``REDIS_URL`` is set,
    otherwise falls back to in-memory :class:`SkillCache`.
    """
    global _global_skill_cache
    with _global_cache_lock:
        if _global_skill_cache is None:
            if _get_redis() is not None:
                try:
                    _global_skill_cache = RedisSkillCache(maxsize=maxsize)
                    logger.info(
                        "Using RedisSkillCache for cross-worker caching"
                    )
                except Exception:
                    _global_skill_cache = SkillCache(maxsize=maxsize)
            else:
                _global_skill_cache = SkillCache(maxsize=maxsize)
        return _global_skill_cache


def warm_skill_cache(
    skill_name: str,
    metadata_list: List[Dict[str, Any]],
    ttl_seconds: float = 300.0,
) -> int:
    """Pre-compute and warm cache for a skill across multiple inputs.

    Uses a thread pool for parallel execution, respecting the shared
    batch pool size limit.
    """
    import concurrent.futures

    cache = get_skill_cache()
    warmed = 0

    def _warm_one(meta: Dict[str, Any]) -> None:
        nonlocal warmed
        try:
            # Only warm if not already cached
            if cache.get(skill_name, meta) is None:
                # Compute key to register it as "warming"
                cache.set(skill_name, meta, {"_warming": True}, ttl_seconds)
                warmed += 1
        except Exception:
            logger.exception("Cache warm failed")

    pool_size = max(
        1,
        min(64, int(os.getenv("UOR_BATCH_POOL_SIZE", "8").strip() or "8")),
    )
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(len(metadata_list), pool_size)
    ) as pool:
        pool.map(_warm_one, metadata_list)
    return warmed


def cached_skill(
    *,
    ttl_seconds: float = 300.0,
    maxsize: int = 1024,
    skip_on_error: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorator that caches a skill's result.

    Args:
        ttl_seconds: Time-to-live for cached entries.
        maxsize: Maximum number of entries in the cache.
        skip_on_error: If ``True``, do not cache results whose
            ``status`` field equals ``"failed"``.
    """

    def decorator(fn: Callable) -> Callable:
        cache = get_skill_cache(maxsize=maxsize)

        @functools.wraps(fn)
        def wrapper(ctx: Any) -> Any:
            metadata = getattr(ctx, "goal", {}).get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            # Try cache read
            cached = cache.get(fn.__name__, metadata)
            if cached is not None:
                return cached

            # Execute
            result = fn(ctx)

            # Store if not an error (and result is a dict)
            if isinstance(result, dict):
                if skip_on_error and result.get("status") == "failed":
                    pass
                else:
                    cache.set(fn.__name__, metadata, result, ttl_seconds)

            return result

        # Attach cache control methods
        _fn_name = fn.__name__
        wrapper.cache_invalidate = (  # type: ignore
            lambda: cache.invalidate(_fn_name)
        )
        wrapper.cache_stats = lambda: cache.stats()  # type: ignore
        return wrapper

    return decorator


# ─── compiled skill cache ─────────────────────────────────────────────────


class CompiledSkillCache:
    """In-memory cache for imported/compiled skill callables.

    Avoids repeated import overhead for lazy-loaded skills by storing
    the resolved callable object keyed by its module path.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, module_path: str) -> Optional[Any]:
        """Return cached skill callable, or None if not compiled."""
        with self._lock:
            return self._cache.get(module_path)

    def set(self, module_path: str, skill: Any) -> None:
        """Cache a compiled skill callable."""
        with self._lock:
            self._cache[module_path] = skill

    def invalidate(self, module_path: str) -> None:
        """Remove a skill from the compiled cache."""
        with self._lock:
            self._cache.pop(module_path, None)

    def clear(self) -> None:
        """Clear all compiled skill entries."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, int]:
        """Return cache stats (size and capacity)."""
        with self._lock:
            return {"size": len(self._cache), "capacity": 0}


_compiled_skill_cache = CompiledSkillCache()
