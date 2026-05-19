"""Result caching system to avoid redundant computations.

This module provides a caching layer for skill execution results,
allowing the system to reuse previously computed results when
the same inputs are provided.
"""

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, Optional


class ResultCache:
    """Cache for skill execution results."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100MB
    ):
        """Initialize the result cache.

        Args:
            cache_dir: Directory to store cache files. If None,
                uses ~/.uar_cache
            ttl_seconds: Time-to-live for cache entries in seconds
            max_entries: Maximum number of cache entries to store
            max_size_bytes: Maximum total size of cache in bytes
        """
        self.cache_dir = cache_dir or os.path.expanduser("~/.uar_cache")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes
        self._lock = threading.Lock()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> str:
        """Generate a unique cache key for a skill execution.

        Args:
            skill_name: Name of the skill
            ctx: Pipeline context
            goal: Goal objective

        Returns:
            Hash string used as cache key

        Note:
            The cache key includes specific context fields known to affect
            skill execution results. Included fields:
            - skill_name: The skill being executed
            - goal: The goal/objective string
            - input_path: If present (affects most skills that process files)
            - file_hashes: If present (affects document processing skills)
            - library_path: If present (affects skills that process libraries)
            - model: If present in context (affects LLM skills)
            - timeout: If present in context (affects skill execution behavior)

            Other context fields are intentionally excluded to allow cache hits
            for skills that don't depend on them.

            IMPORTANT: If a skill depends on additional configuration
            parameters (e.g., API keys, model parameters), those should be
            included in the context before calling cache.get()/set(). The
            executor passes goal metadata to skills, so skills can add
            configuration to context before caching.

            THREAD SAFETY: This method creates a shallow snapshot of relevant
            context fields to avoid race conditions when the context is being
            modified by parallel skill execution.

            IMPORTANT: The dict comprehension at line 100 is NOT guaranteed
            to be atomic in Python. If the context is being modified
            concurrently by other threads during the snapshot, you might get
            inconsistent values. However, this is acceptable for the current
            use case because:
            1. The executor uses ctx_lock for context modifications during
               parallel execution, so modifications are synchronized
            2. Cache key generation happens before parallel execution starts
            3. The snapshot only reads top-level keys, not nested structures

            For true atomicity, the caller should hold ctx_lock during cache
            key generation if concurrent context modifications are possible.
        """
        # Create a shallow snapshot of relevant context fields
        # to avoid race conditions during parallel execution
        # Use a dict comprehension for atomic snapshot of specific keys
        # NOTE: This is only atomic if the caller holds ctx_lock
        relevant_keys = [
            "input_path", "file_hashes", "library_path", "model",
            "timeout", "graphrag_method", "ollama_model",
            "autonomi_network", "autonomi_public", "autonomi_address"
        ]
        ctx_snapshot = {k: ctx.get(k) for k in relevant_keys}

        # Create a deterministic string representation
        # Only include context fields that are known to affect skill execution
        key_data = {
            "skill": skill_name,
            "goal": goal,
        }
        # Add snapshot values (only non-None)
        key_data.update(
            {k: v for k, v in ctx_snapshot.items() if v is not None}
        )

        try:
            key_str = json.dumps(key_data, sort_keys=True)
            return hashlib.sha256(key_str.encode()).hexdigest()
        except (TypeError, ValueError):
            # If context contains non-serializable values, fall back to
            # a more robust key that uses str() for complex values
            # Use str() instead of repr() for more consistent serialization
            fallback_key_parts = [skill_name, goal]
            if "input_path" in ctx:
                fallback_key_parts.append(str(ctx["input_path"]))
            if "library_path" in ctx:
                fallback_key_parts.append(str(ctx["library_path"]))
            if "model" in ctx:
                fallback_key_parts.append(str(ctx["model"]))
            # Add hash of sorted dict keys for determinism
            # Only include serializable top-level keys
            # Snapshot dict items for iteration safety (values are immediately
            # converted to strings, so shallow copy is sufficient)
            try:
                ctx_items_snapshot = list(ctx.items())
                serializable_ctx = {
                    k: str(v) for k, v in ctx_items_snapshot
                    if isinstance(k, (str, int, float, bool))
                }
                ctx_str = json.dumps(serializable_ctx, sort_keys=True)
                ctx_hash = hashlib.sha256(ctx_str.encode()).hexdigest()
                fallback_key_parts.append(ctx_hash)
            except (TypeError, ValueError):
                # If even that fails, use a simple hash of key count
                fallback_key_parts.append(str(len(ctx)))
            fallback_key = ":".join(fallback_key_parts)
            return hashlib.sha256(fallback_key.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """Get the file path for a cache key.

        Args:
            cache_key: Cache key hash

        Returns:
            Full path to cache file
        """
        return os.path.join(self.cache_dir, f"{cache_key}.cache")

    def get(
        self, skill_name: str, ctx: Dict[str, Any], goal: str
    ) -> Optional[Any]:
        """Get cached result if available and not expired.

        Args:
            skill_name: Name of the skill
            ctx: Pipeline context
            goal: Goal objective

        Returns:
            Cached result if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(skill_name, ctx, goal)
        cache_path = self._get_cache_path(cache_key)

        with self._lock:
            if not os.path.exists(cache_path):
                return None

            # Check if cache entry is expired
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age > self.ttl_seconds:
                try:
                    os.remove(cache_path)
                except OSError:
                    pass
                return None

            try:
                with open(cache_path, "r") as f:
                    cached_data = json.load(f)
                    return cached_data.get("result")
            except (json.JSONDecodeError, KeyError, IOError):
                # Cache file corrupted, remove it
                try:
                    os.remove(cache_path)
                except OSError:
                    pass
                return None

    def set(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        goal: str,
        result: Any,
    ) -> None:
        """Cache a skill execution result.

        Args:
            skill_name: Name of the skill
            ctx: Pipeline context
            goal: Goal objective
            result: Result to cache
        """
        cache_key = self._get_cache_key(skill_name, ctx, goal)
        cache_path = self._get_cache_path(cache_key)

        with self._lock:
            # Check if result is JSON-serializable
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                # Skip caching non-serializable results
                return

            # Enforce cache limits before writing
            self._enforce_limits()

            try:
                cached_data = {
                    "result": result,
                    "timestamp": time.time(),
                    "skill": skill_name,
                }
                # Write to temp file first, then atomic rename
                # to prevent corruption if process crashes mid-write
                temp_path = cache_path + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(cached_data, f)
                # Atomic rename is supported on POSIX and Windows
                os.rename(temp_path, cache_path)
            except (IOError, TypeError):
                # Failed to write to cache, silently ignore
                # Clean up temp file if it exists
                temp_path = cache_path + ".tmp"
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass

    def clear(self, skill_name: Optional[str] = None) -> None:
        """Clear cache entries.

        Args:
            skill_name: If provided, only clear entries for this skill.
                If None, clear all cache entries.
        """
        with self._lock:
            if not os.path.exists(self.cache_dir):
                return

            if skill_name:
                # Clear only entries for specific skill
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        cache_path = os.path.join(self.cache_dir, filename)
                        try:
                            with open(cache_path, "r") as f:
                                cached_data = json.load(f)
                                if cached_data.get("skill") == skill_name:
                                    os.remove(cache_path)
                        except (json.JSONDecodeError, IOError):
                            pass
            else:
                # Clear all cache entries
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        cache_path = os.path.join(self.cache_dir, filename)
                        try:
                            os.remove(cache_path)
                        except OSError:
                            pass

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            if not os.path.exists(self.cache_dir):
                return {"total_entries": 0, "total_size_bytes": 0}

            total_entries = 0
            total_size = 0
            skill_counts: Dict[str, int] = {}

            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".cache"):
                    cache_path = os.path.join(self.cache_dir, filename)
                    try:
                        total_entries += 1
                        total_size += os.path.getsize(cache_path)
                        with open(cache_path, "r") as f:
                            cached_data = json.load(f)
                            skill = cached_data.get("skill", "unknown")
                            skill_counts[skill] = (
                                skill_counts.get(skill, 0) + 1
                            )
                    except (json.JSONDecodeError, IOError):
                        pass

            return {
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "skill_counts": skill_counts,
            }

    def _enforce_limits(self) -> None:
        """Enforce cache size and entry limits using LRU eviction.

        Must be called while holding lock.
        """
        if not os.path.exists(self.cache_dir):
            return

        # Get all cache files with their access times
        cache_files = []
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".cache"):
                cache_path = os.path.join(self.cache_dir, filename)
                try:
                    # Use access time (atime) instead of modification time
                    # (mtime) for true LRU behavior - reading from cache
                    # should update last-used timestamp
                    atime = os.path.getatime(cache_path)
                    size = os.path.getsize(cache_path)
                    cache_files.append((cache_path, atime, size))
                except OSError:
                    continue

        # Sort by access time (oldest first for LRU)
        cache_files.sort(key=lambda x: x[1])

        # Remove oldest entries until we're under limits
        total_entries = len(cache_files)
        total_size = sum(size for _, _, size in cache_files)

        removed = 0
        removed_size = 0
        for cache_path, _, size in cache_files:
            # Continue eviction until BOTH limits are satisfied
            if (
                total_entries - removed <= self.max_entries
                and total_size - removed_size <= self.max_size_bytes
            ):
                break
            try:
                os.remove(cache_path)
                removed += 1
                removed_size += size
            except OSError:
                continue


# Global cache instance
_global_cache: Optional[ResultCache] = None
_global_cache_lock = threading.Lock()


def get_cache() -> ResultCache:
    """Get the global cache instance (thread-safe singleton).

    Returns:
        Global ResultCache instance
    """
    global _global_cache
    if _global_cache is None:
        with _global_cache_lock:
            # Double-check after acquiring lock
            if _global_cache is None:
                cache_dir = os.getenv("UAR_CACHE_DIR")
                try:
                    ttl = int(os.getenv("UAR_CACHE_TTL", "3600"))
                except (ValueError, TypeError):
                    ttl = 3600
                try:
                    max_entries = int(
                        os.getenv("UAR_CACHE_MAX_ENTRIES", "1000")
                    )
                except (ValueError, TypeError):
                    max_entries = 1000
                try:
                    max_size = int(
                        os.getenv(
                            "UAR_CACHE_MAX_SIZE",
                            str(100 * 1024 * 1024)
                        )
                    )
                except (ValueError, TypeError):
                    max_size = 100 * 1024 * 1024
                _global_cache = ResultCache(
                    cache_dir=cache_dir,
                    ttl_seconds=ttl,
                    max_entries=max_entries,
                    max_size_bytes=max_size,
                )
    return _global_cache


def clear_global_cache(skill_name: Optional[str] = None) -> None:
    """Clear the global cache.

    Args:
        skill_name: If provided, only clear entries for this skill
    """
    cache = get_cache()
    cache.clear(skill_name=skill_name)
