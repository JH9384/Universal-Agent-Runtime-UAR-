"""Tests for uar.memory.postgres_store.

Mocks all DB connections; no real PostgreSQL required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uar.core.contracts import RunRecord
from uar.memory.postgres_store import (
    _get_db_url,
    _get_read_db_url,
    _shutdown_postgres_pool,
    PostgresRunStore,
)


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = lambda s, *a: None
    conn.cursor.return_value = cur
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    pool = MagicMock()
    pool.getconn.return_value = mock_conn
    return pool


class TestHelpers:
    """Module-level helpers."""

    def test_get_db_url_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert "localhost" in _get_db_url()

    def test_get_db_url_from_env(self, monkeypatch):
        monkeypatch.setenv("UAR_DATABASE_URL", "postgres://host/db")
        assert _get_db_url() == "postgres://host/db"

    def test_get_read_db_url_none(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _get_read_db_url() is None

    def test_get_read_db_url_set(self, monkeypatch):
        monkeypatch.setenv("UAR_DATABASE_READ_URL", "postgres://read/db")
        assert _get_read_db_url() == "postgres://read/db"

    def test_shutdown_pool(self, mock_pool):
        with patch("uar.memory.postgres_store._db_pools", {"url": mock_pool}):
            _shutdown_postgres_pool()
            mock_pool.close.assert_called_once()

    def test_shutdown_pool_none(self):
        with patch("uar.memory.postgres_store._db_pools", {"url": None}):
            _shutdown_postgres_pool()  # must not raise

    def test_shutdown_pool_exception(self, mock_pool):
        mock_pool.close.side_effect = RuntimeError("boom")
        with patch("uar.memory.postgres_store._db_pools", {"url": mock_pool}):
            _shutdown_postgres_pool()  # must not raise


class TestPostgresRunStoreInit:
    """Construction and pool setup."""

    def test_init_creates_pool(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store._pool is mock_pool

    def test_init_read_replica(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch(
                "uar.memory.postgres_store._get_read_db_url",
                return_value="postgres://read/db",
            ):
                store = PostgresRunStore()
                assert store._read_pool is mock_pool

    def test_health_check_pass(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store._health_check() is True

    def test_health_check_fail(self, mock_pool, mock_conn):
        mock_pool.getconn.side_effect = RuntimeError("conn refused")
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            assert store._health_check() is False


class TestPostgresRunStoreWrite:
    """Sync write operations."""

    def test_append(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            record = RunRecord(
                run_id="r1",
                goal_id="g1",
                skills=["s1"],
                status="completed",
            )
            store.append(record)
            mock_conn.commit.assert_called_once()

    def test_append_many(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            records = [
                RunRecord(run_id="r1", goal_id="g1", skills=["s1"],
                          status="completed"),
                RunRecord(run_id="r2", goal_id="g2", skills=["s2"],
                          status="completed"),
            ]
            store.append_many(records)
            mock_conn.cursor.return_value.copy_expert.assert_called_once()

    def test_append_many_empty(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            store.append_many([])
            mock_pool.getconn.assert_not_called()

    def test_flush_noop(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            store.flush()  # no-op, must not raise


class TestPostgresRunStoreRead:
    """Sync read operations."""

    def test_list_records(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.fetchall.return_value = [
            ("r1", "g1", "u1", "ok", "[\"s1\"]", "[]", "{}",
             "{}", None, None, "2024-01-01"),
        ]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            records = store.list_records()
            assert len(records) == 1
            assert records[0]["run_id"] == "r1"
            assert records[0]["skills"] == ["s1"]

    def test_list_records_with_user(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.fetchall.return_value = []
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            records = store.list_records(user_id="u1")
            assert records == []

    def test_list_all_alias(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.fetchall.return_value = []
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            records = store.list_all()
            assert records == []

    def test_get_by_run_id_found(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.fetchone.return_value = (
            "r1", "g1", "u1", "ok", "[]", "[]", "{}",
            "{}", None, None, "2024-01-01",
        )
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            record = store.get_by_run_id("r1")
            assert record is not None
            assert record["run_id"] == "r1"

    def test_get_by_run_id_not_found(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.fetchone.return_value = None
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store.get_by_run_id("nope") is None


class TestPostgresRunStoreDelete:
    """Delete and purge."""

    def test_delete(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.rowcount = 1
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store.delete("r1") is True

    def test_purge_old_records(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.rowcount = 5
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store.purge_old_records(7) == 5

    def test_purge_zero_retention(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            assert store.purge_old_records(0) == 0


class TestPostgresRunStoreFeedback:
    """Recommendation feedback."""

    def test_record_feedback(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            store.record_feedback("rec-1", "accept", "u1")
            assert mock_conn.commit.called

    def test_get_feedback(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = [(1, "rec-1")]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_feedback(recommendation_id="rec-1")
            assert len(results) == 1
            assert results[0]["recommendation_id"] == "rec-1"

    def test_get_feedback_all_params(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"], ["user_id"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = [
            (1, "rec-1", "u1")
        ]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_feedback()
            assert len(results) == 1


class TestPostgresRunStoreShown:
    """Shown recommendations."""

    def test_record_shown(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            store.record_recommendation_shown("rec-1", "u1")
            assert mock_conn.commit.called

    def test_get_shown(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = [(1, "rec-1")]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_shown_recommendations()
            assert len(results) == 1


class TestPostgresRunStoreOutcomes:
    """Outcomes."""

    def test_record_outcome(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            store.record_outcome("rec-1", "resolved")
            assert mock_conn.commit.called

    def test_get_outcomes(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"], ["outcome_type"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = [
            (1, "rec-1", "resolved")
        ]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_outcomes()
            assert len(results) == 1
            assert results[0]["outcome_type"] == "resolved"

    def test_get_outcomes_by_id(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = []
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_outcomes(recommendation_id="rec-1")
            assert results == []


class TestPostgresRunStoreMetadata:
    """Recommendation metadata."""

    def test_record_metadata(self, mock_pool, mock_conn):
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            with patch.object(PostgresRunStore, "_ensure_table"):
                store = PostgresRunStore()
            store.record_recommendation_metadata(
                "rec-1", "category-a", "source", "title", 0.9, "run-1"
            )
            assert mock_conn.commit.called

    def test_get_metadata(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"], ["category"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = [
            (1, "rec-1", "cat-a")
        ]
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_recommendation_metadata()
            assert len(results) == 1

    def test_get_metadata_by_id(self, mock_pool, mock_conn):
        mock_conn.cursor.return_value.description = [
            ["id"], ["recommendation_id"], ["category"]
        ]
        mock_conn.cursor.return_value.fetchall.return_value = []
        with patch(
            "uar.memory.postgres_store._get_sync_pool", return_value=mock_pool
        ):
            store = PostgresRunStore()
            results = store.get_recommendation_metadata(
                recommendation_id="rec-1"
            )
            assert results == []


class _AsyncCtx:
    """Minimal async context manager for mocking pool.acquire()."""

    def __init__(self, obj):
        self._obj = obj

    async def __aenter__(self):
        return self._obj

    async def __aexit__(self, *a):
        pass


class TestPostgresRunStoreAsync:
    """Async operations."""

    @pytest.mark.asyncio
    async def test_append_async(self, mock_pool):
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_async_pool = MagicMock()
        mock_async_pool.acquire.return_value = _AsyncCtx(mock_conn)

        with patch(
            "uar.memory.postgres_store._get_sync_pool",
            return_value=mock_pool,
        ):
            store = PostgresRunStore()
            store._async_pool = mock_async_pool
            record = RunRecord(
                run_id="r1",
                goal_id="g1",
                skills=["s1"],
                status="completed",
            )
            await store.append_async(record)
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_records_async(self, mock_pool):
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[
            ("r1", "g1", "u1", "ok", "[\"s1\"]", "[]", "{}",
             "{}", None, None, "2024-01-01"),
        ])
        mock_async_pool = MagicMock()
        mock_async_pool.acquire.return_value = _AsyncCtx(mock_conn)

        with patch(
            "uar.memory.postgres_store._get_sync_pool",
            return_value=mock_pool,
        ):
            store = PostgresRunStore()
            store._async_pool = mock_async_pool
            records = await store.list_records_async()
            assert len(records) == 1
            assert records[0]["run_id"] == "r1"

    @pytest.mark.asyncio
    async def test_get_by_run_id_async_found(self, mock_pool):
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=(
            "r1", "g1", "u1", "ok", "[]", "[]", "{}",
            "{}", None, None, "2024-01-01",
        ))
        mock_async_pool = MagicMock()
        mock_async_pool.acquire.return_value = _AsyncCtx(mock_conn)

        with patch(
            "uar.memory.postgres_store._get_sync_pool",
            return_value=mock_pool,
        ):
            store = PostgresRunStore()
            store._async_pool = mock_async_pool
            record = await store.get_by_run_id_async("r1")
            assert record is not None
            assert record["run_id"] == "r1"

    @pytest.mark.asyncio
    async def test_get_by_run_id_async_not_found(self, mock_pool):
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_async_pool = MagicMock()
        mock_async_pool.acquire.return_value = _AsyncCtx(mock_conn)

        with patch(
            "uar.memory.postgres_store._get_sync_pool",
            return_value=mock_pool,
        ):
            store = PostgresRunStore()
            store._async_pool = mock_async_pool
            record = await store.get_by_run_id_async("nope")
            assert record is None

    @pytest.mark.asyncio
    async def test_get_async_pool_creates(self, mock_pool):
        with patch(
            "uar.memory.postgres_store._get_sync_pool",
            return_value=mock_pool,
        ):
            store = PostgresRunStore()
            store._async_pool = None
            mock_asyncpg = MagicMock()
            mock_pool_async = MagicMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool_async)
            with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
                pool = await store._get_async_pool()
                assert pool is mock_pool_async
