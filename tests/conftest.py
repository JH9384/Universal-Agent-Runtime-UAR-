"""Pytest configuration for UAR test suite"""

import pytest


def pytest_configure(config):
    """Register custom markers for test categorization."""
    markers = [
        ("slow", "Tests that take >1s or involve I/O"),
        (
            "integration",
            "Tests that exercise external systems or cross-module paths",
        ),
        ("security", "Tests for vulnerabilities, auth, and sandbox behavior"),
        ("api", "Tests for FastAPI endpoints (uses TestClient)"),
        ("store", "Tests for persistence layer (JSON, SQLite, Postgres)"),
        ("skills", "Tests for individual skill functions"),
        (
            "crewai",
            "Tests for CrewAI integration and role-based agent patterns",
        ),
    ]
    for marker, description in markers:
        config.addinivalue_line("markers", f"{marker}: {description}")


def pytest_collection_modifyitems(config, items):
    """Move schemathesis tests to the end to avoid fuzz-state pollution."""
    priority_names = {"test_schemathesis_fuzz"}
    priority = []
    rest = []
    for item in items:
        if any(p in item.nodeid for p in priority_names):
            priority.append(item)
        else:
            rest.append(item)
    items[:] = rest + priority


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state between tests to ensure isolation."""
    from uar.api.middleware import reset_rate_limiter

    reset_rate_limiter()
    yield
