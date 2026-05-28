"""PostgreSQL-backed run store for multi-node UAR deployments.

Uses ``asyncpg`` for async I/O. Falls back to ``psycopg2`` / ``psycopg``
for sync contexts.

Environment:
    UAR_DATABASE_URL — PostgreSQL connection string
        (default: ``postgresql://localhost/uar``)
"""

import importlib.util
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord

logger = logging.getLogger(__name__)

_PG_AVAILABLE = False
_db_pool: Any = None
_pool_lock = threading.Lock()


def _get_db_url() -> str:
    return os.getenv(
        "UAR_DATABASE_URL",
        "postgresql://localhost/uar",
    )


def _get_read_db_url() -> Optional[str]:
    """Read replica URL if configured, otherwise None."""
    return os.getenv("UAR_DATABASE_READ_URL", "").strip() or None


def _get_sync_pool(db_url: str):
    """Lazy singleton threaded connection pool for sync operations."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    with _pool_lock:
        if _db_pool is not None:
            return _db_pool
        if importlib.util.find_spec("psycopg") is not None:
            from psycopg_pool import ConnectionPool  # type: ignore

            _db_pool = ConnectionPool(
                db_url,
                min_size=1,
                max_size=max(
                    1,
                    int(
                        os.getenv("UAR_PG_POOL_SIZE", "10").strip() or "10"
                    ),
                ),
                open=False,
            )
            _db_pool.open()
        elif importlib.util.find_spec("psycopg2") is not None:
            from psycopg2 import pool  # type: ignore

            _db_pool = pool.ThreadedConnectionPool(
                1,
                max(
                    1,
                    int(
                        os.getenv("UAR_PG_POOL_SIZE", "10").strip() or "10"
                    ),
                ),
                db_url,
            )
        else:
            _db_pool = None
        return _db_pool


def _shutdown_postgres_pool() -> None:
    """Close the module-level connection pool on application shutdown."""
    global _db_pool
    with _pool_lock:
        if _db_pool is None:
            return
        try:
            _db_pool.close()
        except Exception:
            logger.exception("Database pool close failed")
        _db_pool = None


class PostgresRunStore:
    """PostgreSQL run store with automatic table creation.

    Schema (one table):
        uar_runs
            id          SERIAL PRIMARY KEY
            run_id      TEXT NOT NULL
            goal_id     TEXT NOT NULL
            user_id     TEXT
            status      TEXT NOT NULL
            skills      JSONB
            events      JSONB
            outputs     JSONB
            metadata    JSONB
            created_at  TIMESTAMPTZ DEFAULT NOW()
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        self._db_url = db_url or _get_db_url()
        self._pool = _get_sync_pool(self._db_url)
        # Optional read replica for offloading SELECT queries
        self._read_url = _get_read_db_url()
        self._read_pool = (
            _get_sync_pool(self._read_url)
            if self._read_url else None
        )
        self._ensure_table()

    def _connect_sync(self):
        """Return a synchronous DBAPI connection from pool."""
        if self._pool is not None:
            return self._pool.getconn()
        try:
            import psycopg
            return psycopg.connect(self._db_url)
        except ImportError:
            import psycopg2  # type: ignore[import-untyped]
            return psycopg2.connect(self._db_url)

    def _connect_read(self):
        """Return read-only connection (replica if configured)."""
        if self._read_pool is not None:
            return self._read_pool.getconn()
        return self._connect_sync()

    def _release_conn(self, conn) -> None:
        """Return connection to pool or close if pool-less."""
        if self._pool is not None:
            self._pool.putconn(conn)
        else:
            conn.close()

    def _release_read_conn(self, conn) -> None:
        """Return read connection to its pool or close."""
        if self._read_pool is not None:
            self._read_pool.putconn(conn)
        else:
            self._release_conn(conn)

    def _health_check(self) -> bool:
        """Proactive health check: ping DB before using connection."""
        conn = None
        try:
            conn = self._connect_sync()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception:
            logger.exception("Postgres health check failed")
            return False
        finally:
            if conn is not None:
                self._release_conn(conn)

    async def _connect_async(self):
        """Return an asyncpg connection (optional dependency)."""
        import asyncpg  # type: ignore[import-untyped]
        return await asyncpg.connect(self._db_url)

    def _ensure_table(self) -> None:
        """Create the runs table if it doesn't exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_runs (
            id          SERIAL PRIMARY KEY,
            run_id      TEXT NOT NULL,
            goal_id     TEXT NOT NULL,
            user_id     TEXT,
            status      TEXT NOT NULL,
            skills      JSONB DEFAULT '[]'::jsonb,
            events      JSONB DEFAULT '[]'::jsonb,
            outputs     JSONB DEFAULT '{}'::jsonb,
            metadata    JSONB DEFAULT '{}'::jsonb,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_uar_runs_run_id
            ON uar_runs(run_id);
        CREATE INDEX IF NOT EXISTS idx_uar_runs_created
            ON uar_runs(created_at DESC);
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def append(self, record: RunRecord) -> None:
        """Insert a run record."""
        data = {
            "run_id": getattr(record, "run_id", getattr(record, "id", "")),
            "goal_id": getattr(
                record, "goal_id",
                getattr(record, "goal", {}).get("id", ""),
            ),
            "user_id": getattr(record, "user_id", None),
            "status": getattr(record, "status", "unknown"),
            "skills": json.dumps(getattr(record, "skills", [])),
            "events": json.dumps(getattr(record, "events", [])),
            "outputs": json.dumps(getattr(record, "outputs", {})),
            "metadata": json.dumps(getattr(record, "metadata", {})),
        }
        sql = """
        INSERT INTO uar_runs (
            run_id, goal_id, user_id, status,
            skills, events, outputs, metadata
        )
        VALUES
            (%(run_id)s, %(goal_id)s, %(user_id)s, %(status)s,
             %(skills)s::jsonb, %(events)s::jsonb,
             %(outputs)s::jsonb, %(metadata)s::jsonb)
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, data)
            conn.commit()
        finally:
            self._release_conn(conn)

    def append_many(self, records: List[RunRecord]) -> None:
        """Bulk insert using COPY FROM for 10-100x faster ingestion."""
        if not records:
            return
        import io

        buf = io.StringIO()
        for record in records:
            fields = [
                getattr(record, "run_id", getattr(record, "id", "")),
                getattr(
                    record, "goal_id",
                    getattr(record, "goal", {}).get("id", ""),
                ),
                getattr(record, "user_id", None) or "",
                getattr(record, "status", "unknown"),
                json.dumps(getattr(record, "skills", [])),
                json.dumps(getattr(record, "events", [])),
                json.dumps(getattr(record, "outputs", {})),
                json.dumps(getattr(record, "metadata", {})),
            ]
            # Tab-delimited, NULL for empty user_id handled above
            buf.write("\t".join(fields) + "\n")
        buf.seek(0)

        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.copy_from(
                    buf,
                    "uar_runs",
                    columns=(
                        "run_id", "goal_id", "user_id", "status",
                        "skills", "events", "outputs", "metadata",
                    ),
                    sep="\t",
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def list_records(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List recent run records."""
        sql = """
        SELECT run_id, goal_id, user_id, status,
               skills, events, outputs, metadata, created_at
        FROM uar_runs
        """
        params: Dict[str, Any] = {}
        if user_id:
            sql += " WHERE user_id = %(user_id)s"
            params["user_id"] = user_id
        sql += " ORDER BY created_at DESC LIMIT %(limit)s"
        params["limit"] = limit

        conn = self._connect_read()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            self._release_read_conn(conn)

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata", "created_at",
        ]
        results = []
        for row in rows:
            record = dict(zip(cols, row))
            for key in ("skills", "events", "outputs", "metadata"):
                if isinstance(record[key], str):
                    record[key] = json.loads(record[key])
            results.append(record)
        return results

    def list_all(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Alias for list_records — satisfies RunStoreProtocol."""
        return self.list_records(user_id=user_id, limit=limit)

    def flush(self) -> None:
        """No-op for API compatibility; Postgres commits are immediate."""

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single record by run ID."""
        sql = """
        SELECT run_id, goal_id, user_id, status,
               skills, events, outputs, metadata, created_at
        FROM uar_runs
        WHERE run_id = %(run_id)s
        ORDER BY created_at DESC
        LIMIT 1
        """
        conn = self._connect_read()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, {"run_id": run_id})
                row = cur.fetchone()
        finally:
            self._release_read_conn(conn)

        if row is None:
            return None

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata", "created_at",
        ]
        record = dict(zip(cols, row))
        for key in ("skills", "events", "outputs", "metadata"):
            if isinstance(record[key], str):
                record[key] = json.loads(record[key])
        return record

    # ------------------------------------------------------------------
    # Async variants (for use in FastAPI / async contexts)
    # ------------------------------------------------------------------

    async def append_async(self, record: RunRecord) -> None:
        """Async insert a run record."""
        data = {
            "run_id": getattr(record, "run_id", getattr(record, "id", "")),
            "goal_id": getattr(
                record, "goal_id",
                getattr(record, "goal", {}).get("id", ""),
            ),
            "user_id": getattr(record, "user_id", None),
            "status": getattr(record, "status", "unknown"),
            "skills": json.dumps(getattr(record, "skills", [])),
            "events": json.dumps(getattr(record, "events", [])),
            "outputs": json.dumps(getattr(record, "outputs", {})),
            "metadata": json.dumps(getattr(record, "metadata", {})),
        }
        sql = """
        INSERT INTO uar_runs (
            run_id, goal_id, user_id, status,
            skills, events, outputs, metadata
        )
        VALUES
            ($1, $2, $3, $4, $5::jsonb, $6::jsonb,
             $7::jsonb, $8::jsonb)
        """
        conn = await self._connect_async()
        try:
            await conn.execute(
                sql,
                data["run_id"],
                data["goal_id"],
                data["user_id"],
                data["status"],
                data["skills"],
                data["events"],
                data["outputs"],
                data["metadata"],
            )
        finally:
            await conn.close()

    async def list_records_async(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Async list recent run records."""
        sql = """
        SELECT run_id, goal_id, user_id, status,
               skills, events, outputs, metadata, created_at
        FROM uar_runs
        """
        params: List[Any] = []
        if user_id:
            sql += " WHERE user_id = $1"
            params.append(user_id)
        sql += " ORDER BY created_at DESC LIMIT ${}".format(
            len(params) + 1
        )
        params.append(limit)

        conn = await self._connect_async()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await conn.close()

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata", "created_at",
        ]
        results = []
        for row in rows:
            record = dict(zip(cols, row))
            for key in ("skills", "events", "outputs", "metadata"):
                if isinstance(record[key], str):
                    record[key] = json.loads(record[key])
            results.append(record)
        return results

    async def get_by_run_id_async(
        self, run_id: str
    ) -> Optional[Dict[str, Any]]:
        """Async fetch a single record by run ID."""
        sql = """
        SELECT run_id, goal_id, user_id, status,
               skills, events, outputs, metadata, created_at
        FROM uar_runs
        WHERE run_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """
        conn = await self._connect_async()
        try:
            row = await conn.fetchrow(sql, run_id)
        finally:
            await conn.close()

        if row is None:
            return None

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata", "created_at",
        ]
        record = dict(zip(cols, row))
        for key in ("skills", "events", "outputs", "metadata"):
            if isinstance(record[key], str):
                record[key] = json.loads(record[key])
        return record
