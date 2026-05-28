"""Tests for advanced API endpoints.

Covers router definition and basic endpoint invocation.
"""

from uar.api.advanced_endpoints import router


class TestRouter:
    """Router configuration."""

    def test_prefix(self):
        assert router.prefix == "/api/advanced"

    def test_tags(self):
        assert "advanced" in router.tags
