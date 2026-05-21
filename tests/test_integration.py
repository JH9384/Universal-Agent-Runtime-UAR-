"""Integration tests for UAR components.

Tests WebSocket and cache modules in an integrated manner.
"""

import pytest
import tempfile
from pathlib import Path
from uar.core.cache import ResultCache


class TestCacheIntegration:
    """Integration tests for ResultCache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create ResultCache instance with temp directory."""
        return ResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=3600,
            max_entries=1000,
            max_size_bytes=100 * 1024 * 1024,
        )

    def test_cache_write_and_read(self, cache):
        """Test writing and reading from cache."""
        skill_name = "test_skill"
        context = {"input": "test"}
        goal = "test goal"
        result = {"output": "test output"}

        # Write to cache
        cache.set(skill_name, context, goal, result)

        # Read from cache
        cached_result = cache.get(skill_name, context, goal)
        assert cached_result == result

    def test_cache_hit_and_miss(self, cache):
        """Test cache hit and miss scenarios."""
        skill_name = "test_skill"
        context = {"input": "test"}
        goal = "test goal"
        result = {"output": "test output"}

        # Cache miss
        assert cache.get(skill_name, context, goal) is None

        # Write to cache
        cache.set(skill_name, context, goal, result)

        # Cache hit
        assert cache.get(skill_name, context, goal) == result

    def test_cache_key_different_context(self, cache):
        """Test that different contexts produce different cache keys."""
        skill_name = "test_skill"
        goal = "test goal"
        result = {"output": "test output"}

        # Write with context A (using input_path which is in cache key)
        context_a = {"input_path": "A"}
        cache.set(skill_name, context_a, goal, result)

        # Read with context B should miss
        context_b = {"input_path": "B"}
        assert cache.get(skill_name, context_b, goal) is None

    @pytest.mark.skip(
        reason="Cache eviction requires file-based LRU implementation"
    )
    def test_cache_eviction(self, cache):
        """Test cache eviction when limits are exceeded."""
        cache_small = ResultCache(
            cache_dir=cache.cache_dir,
            ttl_seconds=3600,
            max_entries=2,
            max_size_bytes=1024,
        )

        # Add 3 entries (exceeds max_entries)
        # Use input_path to ensure different cache keys
        for i in range(3):
            cache_small.set(
                f"skill_{i}",
                {"input_path": f"test_{i}"},
                f"goal_{i}",
                {"output": f"result_{i}"},
            )

        # First entry should be evicted (LRU based on write time)
        assert (
            cache_small.get("skill_0", {"input_path": "test_0"}, "goal_0")
            is None
        )
        assert (
            cache_small.get("skill_1", {"input_path": "test_1"}, "goal_1")
            is not None
        )
        assert (
            cache_small.get("skill_2", {"input_path": "test_2"}, "goal_2")
            is not None
        )


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection can be established."""
        # This is a placeholder for actual WebSocket integration test
        # Would require running the actual server
        pytest.skip("Requires running server")

    @pytest.mark.asyncio
    async def test_websocket_message_flow(self):
        """Test WebSocket message flow."""
        # This is a placeholder for actual WebSocket message flow test
        pytest.skip("Requires running server")


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_cache_with_complex_data(self):
        """Test cache with complex nested data structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResultCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=3600,
                max_entries=100,
                max_size_bytes=10 * 1024 * 1024,
            )

            complex_result = {
                "nested": {"data": [1, 2, 3], "metadata": {"key": "value"}},
                "list": [{"a": 1}, {"b": 2}],
            }

            cache.set(
                "complex_skill",
                {"ctx": "data"},
                "complex_goal",
                complex_result,
            )
            cached = cache.get(
                "complex_skill", {"ctx": "data"}, "complex_goal"
            )

            assert cached == complex_result
            assert cached["nested"]["data"] == [1, 2, 3]
