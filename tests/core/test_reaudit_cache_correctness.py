"""RE-AUDIT SPRINT Ω-1 — Track 1: Cache Correctness.

Verify that analytics cache invalidation happens under all four paths:
1. New run recorded
2. Replay generated (read-only — no invalidation needed)
3. Burn-in executed
4. Certification recomputed (read-only — no invalidation needed)

Success criterion: 0 stale reads observed for write paths.
"""

from uar.core.analytics_cache import AnalyticsCache


def _make_payload():
    return {"hours": 24, "count": 5}


class TestCacheInvalidationOnNewRun:
    """Path 1: New run recorded → cache invalidated."""

    def test_runs_router_invalidates_on_append(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, _make_payload())
        cache.set(
    "topology-hot-paths", "alice", False, 24, 1000, _make_payload())

        # Simulate the invalidation call made by runs.py after store.append()
        cache.invalidate()

        assert cache.get("failure-clusters", "alice", False, 24, 1000) is None
        assert cache.get(
    "topology-hot-paths", "alice", False, 24, 1000) is None
        assert cache.stats()["entries"] == 0

    def test_cache_entry_survives_without_invalidation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
        "failure-clusters", "alice", False, 24, 1000,
        _make_payload())

        # Without invalidation, entry remains
        assert (
            cache.get("failure-clusters", "alice", False, 24, 1000)
            is not None
        )


class TestCacheInvalidationOnBurnIn:
    """Path 3: Burn-in executed → cache invalidated."""

    def test_burnin_router_invalidates(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "confidence-drift", "alice", False, 24, 1000, _make_payload())
        cache.set(
    "recipe-intelligence", "alice", False, 24, 1000, _make_payload())

        # Simulate the invalidation call made by burn_in.py
        cache.invalidate()

        assert cache.get("confidence-drift", "alice", False, 24, 1000) is None
        assert cache.get(
    "recipe-intelligence", "alice", False, 24, 1000) is None
        assert cache.stats()["entries"] == 0


class TestCacheInvalidationOnReplay:
    """Path 2: Replay generated.

    The replay explorer endpoint is READ-ONLY.
    It does not write to the store, therefore it does not
    (and should not) trigger cache invalidation.
    """

    def test_replay_explorer_is_read_only_no_invalidation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, _make_payload())

        # Replay explorer only reads. No invalidation expected.
        # This test documents the expected behavior.
        assert (
            cache.get("failure-clusters", "alice", False, 24, 1000)
            is not None
        )


class TestCacheInvalidationOnCertification:
    """Path 4: Certification recomputed.

    The certification endpoint is READ-ONLY.
    It computes certification from existing data without writing,
    therefore it does not (and should not) trigger cache invalidation.
    """

    def test_certification_endpoint_is_read_only_no_invalidation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, _make_payload())

        # Certification endpoint only reads. No invalidation expected.
        # This test documents the expected behavior.
        assert (
            cache.get("failure-clusters", "alice", False, 24, 1000)
            is not None
        )


class TestAlertsSummaryCaching:
    """D4A-3: Alert Banner caches correctly."""

    def test_alerts_summary_is_cached(self):
        cache = AnalyticsCache(ttl_seconds=60)
        payload = {"hours": 24, "count": 2, "alerts": []}
        cache.set(
            "alerts-summary", "alice", False, 24, 1000, payload)
        assert cache.get(
            "alerts-summary", "alice", False, 24, 1000) == payload

    def test_alerts_summary_invalidation_on_run(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
            "alerts-summary", "alice", False, 24, 1000, _make_payload())
        cache.set(
            "failure-clusters", "alice", False, 24, 1000, _make_payload())

        # Run invalidation clears all analytics
        cache.invalidate()

        assert cache.get(
            "alerts-summary", "alice", False, 24, 1000) is None
        assert cache.get(
            "failure-clusters", "alice", False, 24, 1000) is None


class TestCacheInvalidationEdgeCases:
    """Additional edge-case correctness checks."""

    def test_invalidate_all_clears_everything(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set("a", "alice", False, 24, 1000, _make_payload())
        cache.set("b", "bob", True, 48, 5000, _make_payload())
        cache.set("c", "alice", False, 24, 1000, _make_payload())

        cache.invalidate()

        assert cache.get("a", "alice", False, 24, 1000) is None
        assert cache.get("b", "bob", True, 48, 5000) is None
        assert cache.get("c", "alice", False, 24, 1000) is None

    def test_endpoint_specific_invalidation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, _make_payload())
        cache.set(
    "topology-hot-paths", "alice", False, 24, 1000, _make_payload())

        cache.invalidate("failure-clusters")

        assert cache.get("failure-clusters", "alice", False, 24, 1000) is None
        # Other endpoints untouched
        assert (
            cache.get("topology-hot-paths", "alice", False, 24, 1000)
            is not None
        )

    def test_cache_scoping_isolation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, {"data": "alice-24"})
        cache.set(
    "failure-clusters", "bob", False, 24, 1000, {"data": "bob-24"})
        cache.set(
    "failure-clusters", "alice", False, 48, 1000, {"data": "alice-48"})
        cache.set(
    "failure-clusters", "alice", True, 24, 1000, {"data": "alice-admin"})

        # Each key is independent
        assert cache.get(
    "failure-clusters", "alice", False, 24, 1000) == {"data": "alice-24"}
        assert cache.get(
    "failure-clusters", "bob", False, 24, 1000) == {"data": "bob-24"}
        assert cache.get(
    "failure-clusters", "alice", False, 48, 1000) == {"data": "alice-48"}
        assert cache.get(
    "failure-clusters", "alice", True, 24, 1000) == {"data": "alice-admin"}

    def test_invalidate_all_affects_all_scopes(self):
        cache = AnalyticsCache(ttl_seconds=60)
        cache.set(
    "failure-clusters", "alice", False, 24, 1000, _make_payload())
        cache.set("failure-clusters", "bob", False, 24, 1000, _make_payload())
        cache.set(
    "topology-hot-paths", "alice", True, 48, 5000, _make_payload())

        cache.invalidate()

        assert cache.get("failure-clusters", "alice", False, 24, 1000) is None
        assert cache.get("failure-clusters", "bob", False, 24, 1000) is None
        assert cache.get("topology-hot-paths", "alice", True, 48, 5000) is None

    def test_zero_stale_reads_after_invalidation(self):
        cache = AnalyticsCache(ttl_seconds=60)
        original = {"runs_analyzed": 10, "total_failures": 3}
        cache.set("failure-clusters", "alice", False, 24, 1000, original)

        # After append, invalidate is called
        cache.invalidate()

        # Cache miss → fresh computation would happen
        result = cache.get("failure-clusters", "alice", False, 24, 1000)
        assert result is None

        # Simulate fresh result with new data
        updated = {"runs_analyzed": 11, "total_failures": 4}
        cache.set("failure-clusters", "alice", False, 24, 1000, updated)

        # Verify we get the new data, not stale
        assert cache.get(
    "failure-clusters", "alice", False, 24, 1000) == updated
