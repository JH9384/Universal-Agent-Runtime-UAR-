"""Performance regression tests for UAR.

Tests to ensure performance doesn't degrade over time.
"""

import pytest
import time
import tempfile
from pathlib import Path
from uar.core.cache import ResultCache
from uar.core.registry import SkillRegistry


class TestCachePerformance:
    """Performance tests for ResultCache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_cache_get_performance(self, temp_cache_dir):
        """Test cache get performance should be fast."""
        cache = ResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=3600,
            max_entries=1000,
            max_size_bytes=100 * 1024 * 1024
        )

        # Pre-populate cache
        for i in range(100):
            cache.set(
                f"skill_{i}",
                {"input": f"test_{i}"},
                f"goal_{i}",
                {"output": f"result_{i}"}
            )

        # Measure get performance
        start = time.time()
        for i in range(100):
            cache.get(f"skill_{i}", {"input": f"test_{i}"}, f"goal_{i}")
        duration = time.time() - start

        # Should complete 100 gets in less than 1 second
        assert duration < 1.0, f"Cache get too slow: {duration:.3f}s"

    def test_cache_set_performance(self, temp_cache_dir):
        """Test cache set performance should be fast."""
        cache = ResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=3600,
            max_entries=1000,
            max_size_bytes=100 * 1024 * 1024
        )

        # Measure set performance
        start = time.time()
        for i in range(100):
            cache.set(
                f"skill_{i}",
                {"input": f"test_{i}"},
                f"goal_{i}",
                {"output": f"result_{i}"}
            )
        duration = time.time() - start

        # Should complete 100 sets in less than 1 second
        assert duration < 1.0, f"Cache set too slow: {duration:.3f}s"


class TestRegistryPerformance:
    """Performance tests for SkillRegistry."""

    def test_registry_lookup_performance(self):
        """Test registry lookup performance should be fast."""
        registry = SkillRegistry()

        # Register skills
        for i in range(100):
            registry.register(f"skill_{i}", lambda ctx: {"result": "test"})

        # Measure lookup performance
        start = time.time()
        for i in range(1000):
            registry.get(f"skill_{i % 100}")
        duration = time.time() - start

        # Should complete 1000 lookups in less than 0.1 seconds
        assert duration < 0.1, f"Registry lookup too slow: {duration:.3f}s"

    def test_registry_list_performance(self):
        """Test registry list performance should be fast."""
        registry = SkillRegistry()

        # Register skills
        for i in range(100):
            registry.register(f"skill_{i}", lambda ctx: {"result": "test"})

        # Measure list performance
        start = time.time()
        for _ in range(1000):
            registry.list()
        duration = time.time() - start

        # Should complete 1000 lists in less than 0.1 seconds
        assert duration < 0.1, f"Registry list too slow: {duration:.3f}s"
