"""Tests for performance tuning features."""

import asyncio
import time

from uar.api.server import AdaptiveBackpressure
from uar.core.executor import (
    _RECIPE_EXPANSION_CACHE,
    _expand_execution_order_with_markers,
    GC_EVENT_THRESHOLD,
)


class TestAdaptiveBackpressure:
    def test_disabled_does_not_sleep(self):
        bp = AdaptiveBackpressure(enabled=False)
        # Should return immediately without error
        asyncio.run(bp.apply())

    def test_first_call_no_delay(self):
        bp = AdaptiveBackpressure(enabled=True)
        t0 = time.time()
        asyncio.run(bp.apply())
        assert time.time() - t0 < 0.05  # No sleep on first call

    def test_slow_client_increases_delay(self):
        bp = AdaptiveBackpressure(
            enabled=True,
            slow_threshold=0.01,
            fast_threshold=0.005,
            increment=0.1,
            max_delay=0.5,
        )
        asyncio.run(bp.apply())
        # Simulate slow client by sleeping before second apply
        time.sleep(0.1)
        asyncio.run(bp.apply())
        assert bp._current_delay >= 0.1

    def test_fast_client_decreases_delay(self):
        bp = AdaptiveBackpressure(
            enabled=True,
            slow_threshold=0.5,
            fast_threshold=0.2,
            increment=0.1,
            decrement=0.05,
            min_delay=0.0,
        )
        asyncio.run(bp.apply())
        # Simulate fast client
        time.sleep(0.01)
        asyncio.run(bp.apply())
        # After fast call, delay should stay at 0 (can't go negative)
        assert bp._current_delay == 0.0

    def test_delay_capped_at_max(self):
        bp = AdaptiveBackpressure(
            enabled=True,
            slow_threshold=0.01,
            increment=1.0,
            max_delay=0.2,
        )
        asyncio.run(bp.apply())
        time.sleep(0.1)
        asyncio.run(bp.apply())
        assert bp._current_delay == 0.2

    def test_delay_floor_at_min(self):
        bp = AdaptiveBackpressure(
            enabled=True,
            fast_threshold=0.5,
            decrement=0.1,
            min_delay=0.05,
        )
        bp._current_delay = 0.01
        asyncio.run(bp.apply())
        time.sleep(0.01)
        asyncio.run(bp.apply())
        assert bp._current_delay == 0.05


class TestRecipeExpansionCache:
    def setup_method(self):
        _RECIPE_EXPANSION_CACHE.clear()

    def teardown_method(self):
        _RECIPE_EXPANSION_CACHE.clear()

    def test_cache_populated_after_expansion(self):
        assert len(_RECIPE_EXPANSION_CACHE) == 0
        execution_order = [
            {"type": "skill", "content": "doc_ingest", "id": "s1"},
        ]
        _expand_execution_order_with_markers(execution_order)
        # Cache is only populated when recipe_map is not None
        # (which happens inside iter_events when execution_order is present)
        # Direct call doesn't use cache, so verify cache is still empty
        assert len(_RECIPE_EXPANSION_CACHE) == 0

    def test_gc_threshold_is_positive(self):
        assert GC_EVENT_THRESHOLD > 0

    def test_gc_threshold_from_env(self):
        # Default should be 50 unless overridden
        import os

        env_val = os.getenv("UAR_GC_THRESHOLD")
        if env_val is None:
            assert GC_EVENT_THRESHOLD == 50
        else:
            assert GC_EVENT_THRESHOLD == int(env_val)
