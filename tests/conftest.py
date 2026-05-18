"""Pytest configuration for UAR test suite"""

import pytest


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state between tests to ensure isolation."""
    from uar.api.middleware import reset_rate_limiter

    reset_rate_limiter()
    yield
