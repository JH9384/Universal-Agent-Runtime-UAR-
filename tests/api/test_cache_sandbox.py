"""Tests for cache and sandbox router.

Covers router definition.
"""

from uar.api.routers.cache_sandbox import router


class TestRouter:
    """Router configuration."""

    def test_routes_exist(self):
        routes = [r.path for r in router.routes]
        assert "/api/cache/stats" in routes
        assert "/api/cache/invalidate" in routes
        assert "/api/sandbox/health" in routes
        assert "/api/sandbox/eval" in routes
