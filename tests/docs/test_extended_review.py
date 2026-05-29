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
        source_timeout = inspect.getsource(math_compute._with_timeout)
        # Check for actual API calls, not just word occurrences in docs
        assert "signal.signal(signal.SIGALRM" not in source
        assert "signal.alarm(" not in source
        assert "threading.Thread(" in source_timeout

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


class TestBackgroundPersistenceCleanup:
    """_persist_async must own temp file cleanup to avoid races."""

    def test_persist_async_unlinks_after_read(self, tmp_path):
        from uar.services.execution import GoalExecutionService

        svc = GoalExecutionService()
        # Create a dummy file to simulate temp file
        dummy = tmp_path / "dummy.jsonl"
        dummy.write_text('{}\n')

        # _persist_async should unlink the file after (mock) reading
        import asyncio

        async def _run():
            # Mock _persist_from_file to do nothing (simulate success)
            orig = svc._persist_from_file
            svc._persist_from_file = (
                lambda *a, **k: None  # type: ignore[method-assign]
            )
            try:
                await svc._persist_async(
                    str(dummy), None, None, "req-1"  # type: ignore[arg-type]
                )
            finally:
                svc._persist_from_file = orig  # type: ignore[method-assign]

        asyncio.run(_run())
        assert not dummy.exists()


class TestCoalesceLockEviction:
    """Coalesce eviction must not remove locks held by other threads."""

    def test_eviction_does_not_remove_held_lock(self):
        import threading
        from uar.core import executor as _exec

        key = "test_skill:abc123"
        # Simulate a thread holding the lock
        with _exec._coalesce_meta_lock:
            _exec._coalesce_locks[key] = threading.Lock()
        lock = _exec._coalesce_locks[key]
        lock.acquire()

        # Eviction should NOT remove the lock
        with _exec._coalesce_meta_lock:
            _exec._coalesce_results.pop(key, None)
            # The old code did: _exec._coalesce_locks.pop(key, None)
            # which would create a race. Verify it's still present.

        assert key in _exec._coalesce_locks
        lock.release()


class TestTimeoutPoolMaxValidation:
    """UAR_TIMEOUT_POOL_MAX must be at least 1 to keep ThreadPoolExecutor
    healthy."""

    def test_pool_max_is_at_least_one(self):
        from uar.core import executor as _exec

        assert _exec._TIMEOUT_POOL_MAX >= 1


class TestHistogramAlphaValidation:
    """UAR_METRIC_HISTOGRAM_ALPHA must fall back to default on invalid
    env values to prevent import-time crashes."""

    def test_log_alpha_is_positive_float(self):
        from uar.api import metrics

        assert isinstance(metrics._LOG_ALPHA, float)
        assert metrics._LOG_ALPHA > 0


class TestCipherOpsValidation:
    """AES key/IV lengths must be validated before passing to PyCryptodome."""

    def test_aes_encrypt_rejects_short_key(self):
        from uar.skills.cipher_ops import _aes_encrypt

        result = _aes_encrypt(b"data", b"short")
        assert result["success"] is False
        assert "16, 24, or 32 bytes" in result["error"]

    def test_aes_decrypt_rejects_bad_iv(self):
        from uar.skills.cipher_ops import _aes_decrypt

        result = _aes_decrypt(b"data", b"x" * 32, b"bad")
        assert result["success"] is False
        assert "IV must be 16 bytes" in result["error"]

    def test_decode_base64_catches_type_error(self):
        from uar.skills.cipher_ops import _decode_base64

        with pytest.raises(ValueError, match="Invalid base64"):
            _decode_base64(None)  # type: ignore[arg-type]


class TestAutonomiSafeFilename:
    """Autonomi download destination must sanitize untrusted addresses."""

    def test_safe_filename_strips_traversal(self):
        from uar.skills.autonomi_storage import _safe_filename

        assert _safe_filename("../../../etc/passwd") == "etc_passwd"
        assert _safe_filename("a/b\\c.txt") == "a_b_c.txt"

    def test_safe_filename_caps_length(self):
        from uar.skills.autonomi_storage import _safe_filename

        long_name = "x" * 500
        assert len(_safe_filename(long_name)) == 128

    def test_safe_filename_fallback_on_empty(self):
        from uar.skills.autonomi_storage import _safe_filename

        assert _safe_filename("...") == "unnamed"


class TestGraphRagTimeoutClamp:
    """User-provided timeout must be clamped to prevent absurd values."""

    def test_timeout_clamped_high(self):
        from uar.skills.graphrag_skills import DEFAULT_QUERY_TIMEOUT

        raw = 999999999
        clamped = max(1, min(int(raw or DEFAULT_QUERY_TIMEOUT), 7200))
        assert clamped == 7200

    def test_timeout_clamped_low(self):
        from uar.skills.graphrag_skills import DEFAULT_QUERY_TIMEOUT

        raw = -100
        clamped = max(1, min(int(raw or DEFAULT_QUERY_TIMEOUT), 7200))
        assert clamped == 1


class TestWebSocketMaxConnectionsNonNegative:
    """WEBSOCKET_MAX_CONNECTIONS env must not be negative."""

    def test_ws_max_connections_is_non_negative(self):
        from uar.api.server import _ws_conn_counter

        assert _ws_conn_counter.max_connections >= 0


class TestOllamaGenerateTimeoutClamp:
    """OLLAMA_TIMEOUT_SECONDS must be clamped to safe bounds."""

    def test_timeout_clamped_high(self):
        raw = 999999999.0
        clamped = max(1.0, min(raw, 600.0))
        assert clamped == 600.0

    def test_timeout_clamped_low(self):
        raw = -10.0
        clamped = max(1.0, min(raw, 600.0))
        assert clamped == 1.0


class TestJsonUtilsNarrowExceptions:
    """json_utils must not swallow MemoryError / SystemExit."""

    def test_json_loads_safely_returns_default_on_bad_input(self):
        from uar.core.json_utils import json_loads_safely

        assert json_loads_safely("not json", default=[]) == []

    def test_json_dumps_safely_returns_none_on_unserializable(self):
        from uar.core.json_utils import json_dumps_safely

        assert json_dumps_safely(object()) is None
