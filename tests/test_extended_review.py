"""Regression tests for extended review findings.

Covers HTTP client lifecycle, resource cleanup, thread-safe timeouts,
and production-safe runtime checks.
"""

from unittest.mock import MagicMock

import pytest


class TestUorEcosystemHTTPClientLifecycle:
    """Module-level httpx client must be closable without error."""

    def test_close_http_client_idempotent(self):
        from uar.core.uor_ecosystem import _close_http_client

        # Should not raise even when client was never created
        _close_http_client()

    def test_close_http_client_clears_reference(self, monkeypatch):
        from uar.core import uor_ecosystem as mod

        mock_client = MagicMock()
        monkeypatch.setattr(mod, "_http_client", mock_client)
        mod._close_http_client()
        mock_client.close.assert_called_once()
        assert mod._http_client is None


class TestAtomicLangModelHTTPClientLifecycle:
    """ALM module-level httpx client must be closable without error."""

    def test_close_http_client_idempotent(self):
        from uar.skills.atomic_lang_model import _close_http_client

        _close_http_client()

    def test_close_http_client_clears_reference(self, monkeypatch):
        from uar.skills import atomic_lang_model as mod

        mock_client = MagicMock()
        monkeypatch.setattr(mod, "_http_client", mock_client)
        mod._close_http_client()
        mock_client.close.assert_called_once()
        assert mod._http_client is None


class TestMathComputeTimeout:
    """SymPy timeout must work without SIGALRM (cross-platform)."""

    def test_timeout_uses_threading_not_signal(self):
        """The implementation should use threading, not signal.SIGALRM."""
        import inspect
        from uar.skills import math_compute

        source = inspect.getsource(math_compute._safe_sympy_eval)
        # Check for actual API calls, not just word occurrences in docs
        assert "signal.signal(signal.SIGALRM" not in source
        assert "signal.alarm(" not in source
        assert "threading.Thread(" in source

    def test_fast_expr_returns_success(self):
        from uar.skills.math_compute import _safe_sympy_eval

        result = _safe_sympy_eval("2 + 2", timeout=5.0)
        assert result["success"] is True
        assert result["result"] == "4"


class TestDistributedWorkerPool:
    """WorkerPool must raise RuntimeError instead of assert."""

    def test_submit_raises_runtime_error_when_executor_none(self):
        from uar.core.distributed import WorkerPool

        pool = WorkerPool(max_workers=1)
        pool._executor = None
        # Mock _ensure_executor so it does NOT recreate the executor
        pool._ensure_executor = lambda: None  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="failed to initialize"):
            pool.submit(None)  # type: ignore[arg-type]


class TestSqliteStoreReadPoolCleanup:
    """SqliteRunStore.close() must drain reader pool connections."""

    def test_close_drains_reader_pool(self, tmp_path):
        from uar.memory.sqlite_store import SqliteRunStore

        store = SqliteRunStore(path=str(tmp_path / "test.db"))
        # Add a fake connection to the pool to verify cleanup
        import sqlite3

        fake_conn = sqlite3.connect(":memory:")
        store._read_pool.put(fake_conn)
        store.close()
        assert store._read_pool.empty()
        # Connection should be closed (any operation would raise)
        with pytest.raises(sqlite3.ProgrammingError):
            fake_conn.execute("SELECT 1")
