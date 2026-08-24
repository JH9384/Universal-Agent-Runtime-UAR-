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


@pytest.fixture(autouse=True)
def close_sqlite_stores(monkeypatch):
    """Close every SQLite store created by a test before the next test.

    The store owns a background writer and a reader pool.  Tests often pass a
    short-lived store directly into the unit under test, so relying on
    ``__del__`` leaves those resources alive because the writer thread holds a
    bound-method reference to the store.
    """
    from uar.memory.sqlite_store import SqliteRunStore

    created = []
    original_init = SqliteRunStore.__init__

    def tracked_init(store, *args, **kwargs):
        original_init(store, *args, **kwargs)
        created.append(store)

    monkeypatch.setattr(SqliteRunStore, "__init__", tracked_init)
    yield

    for store in reversed(created):
        try:
            store.close()
        except Exception:
            # A few negative-path tests deliberately poison internals.  Their
            # assertions remain authoritative; cleanup is best effort.
            pass
