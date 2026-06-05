"""PostgreSQL-backed run store for multi-node UAR deployments.

Uses ``asyncpg`` for async I/O. Falls back to ``psycopg2`` / ``psycopg``
for sync contexts.

Environment:
    UAR_DATABASE_URL — PostgreSQL connection string
        (default: ``postgresql://localhost/uar``)
"""

import atexit
import importlib.util
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord

logger = logging.getLogger(__name__)

_PG_AVAILABLE = False
_db_pools: Dict[str, Any] = {}
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
    """Lazy per-URL threaded connection pool for sync operations."""
    global _db_pools
    with _pool_lock:
        if db_url in _db_pools:
            return _db_pools[db_url]
        if importlib.util.find_spec("psycopg") is not None:
            from psycopg_pool import ConnectionPool  # type: ignore

            pool = ConnectionPool(
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
            pool.open()
            _db_pools[db_url] = pool
        elif importlib.util.find_spec("psycopg2") is not None:
            from psycopg2 import pool as _pool  # type: ignore

            _db_pools[db_url] = _pool.ThreadedConnectionPool(
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
            _db_pools[db_url] = None
        return _db_pools[db_url]


def _shutdown_postgres_pool() -> None:
    """Close all module-level connection pools on application shutdown."""
    global _db_pools
    with _pool_lock:
        for url, pool in list(_db_pools.items()):
            if pool is None:
                continue
            try:
                pool.close()
            except Exception:
                logger.exception("Database pool close failed for %s", url)
        _db_pools.clear()


atexit.register(_shutdown_postgres_pool)


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
        self._async_pool: Optional[Any] = None
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

    async def _get_async_pool(self):
        """Lazy asyncpg pool; created on first async call."""
        if self._async_pool is not None:
            return self._async_pool
        import asyncpg  # type: ignore[import-untyped]
        self._async_pool = await asyncpg.create_pool(
            self._db_url,
            min_size=1,
            max_size=max(
                1,
                int(
                    os.getenv("UAR_PG_POOL_SIZE", "10").strip() or "10"
                ),
            ),
        )
        return self._async_pool

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
            uor_address TEXT,
            uor_witness JSONB,
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
        _witness = getattr(record, "uor_witness", None)
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
            "uor_address": getattr(record, "uor_address", None),
            "uor_witness": (
                json.dumps(_witness) if _witness is not None else None
            ),
        }
        sql = """
        INSERT INTO uar_runs (
            run_id, goal_id, user_id, status,
            skills, events, outputs, metadata,
            uor_address, uor_witness
        )
        VALUES
            (%(run_id)s, %(goal_id)s, %(user_id)s, %(status)s,
             %(skills)s::jsonb, %(events)s::jsonb,
             %(outputs)s::jsonb, %(metadata)s::jsonb,
             %(uor_address)s, %(uor_witness)s::jsonb)
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
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
        for record in records:
            _addr = getattr(record, "uor_address", None)
            _witness = getattr(record, "uor_witness", None)
            fields = [
                getattr(record, "run_id", "") or getattr(record, "id", ""),
                getattr(record, "goal_id", "")
                or getattr(record, "goal", {}).get("id", ""),
                getattr(record, "user_id", None) or r"\N",
                getattr(record, "status", "unknown"),
                json.dumps(getattr(record, "skills", [])),
                json.dumps(getattr(record, "events", [])),
                json.dumps(getattr(record, "outputs", {})),
                json.dumps(getattr(record, "metadata", {})),
                _addr if _addr is not None else r"\N",
                json.dumps(_witness) if _witness is not None else r"\N",
            ]
            writer.writerow(fields)
        buf.seek(0)

        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.copy_expert(
                    "COPY uar_runs"
                    " (run_id, goal_id, user_id, status,"
                    "  skills, events, outputs, metadata,"
                    "  uor_address, uor_witness)"
                    " FROM STDIN WITH (FORMAT CSV, DELIMITER '\t',"
                    "  NULL '\\N')",
                    buf,
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
               skills, events, outputs, metadata,
               uor_address, uor_witness, created_at
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
            "skills", "events", "outputs", "metadata",
            "uor_address", "uor_witness", "created_at",
        ]
        results = []
        for row in rows:
            record = dict(zip(cols, row, strict=True))
            for key in (
                "skills", "events", "outputs", "metadata", "uor_witness"
            ):
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
               skills, events, outputs, metadata,
               uor_address, uor_witness, created_at
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
            "skills", "events", "outputs", "metadata",
            "uor_address", "uor_witness", "created_at",
        ]
        record = dict(zip(cols, row, strict=True))
        for key in (
            "skills", "events", "outputs", "metadata", "uor_witness"
        ):
            if isinstance(record[key], str):
                record[key] = json.loads(record[key])
        return record

    # ------------------------------------------------------------------
    # Async variants (for use in FastAPI / async contexts)
    # ------------------------------------------------------------------

    async def append_async(self, record: RunRecord) -> None:
        """Async insert a run record."""
        _witness = getattr(record, "uor_witness", None)
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
            "uor_address": getattr(record, "uor_address", None),
            "uor_witness": (
                json.dumps(_witness) if _witness is not None else None
            ),
        }
        sql = """
        INSERT INTO uar_runs (
            run_id, goal_id, user_id, status,
            skills, events, outputs, metadata,
            uor_address, uor_witness
        )
        VALUES
            ($1, $2, $3, $4, $5::jsonb, $6::jsonb,
             $7::jsonb, $8::jsonb, $9, $10::jsonb)
        """
        pool = await self._get_async_pool()
        async with pool.acquire() as conn:
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
                data["uor_address"],
                data["uor_witness"],
            )

    async def list_records_async(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Async list recent run records."""
        sql = """
        SELECT run_id, goal_id, user_id, status,
               skills, events, outputs, metadata,
               uor_address, uor_witness, created_at
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

        pool = await self._get_async_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata",
            "uor_address", "uor_witness", "created_at",
        ]
        results = []
        for row in rows:
            record = dict(zip(cols, row, strict=True))
            for key in (
                "skills", "events", "outputs", "metadata", "uor_witness"
            ):
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
               skills, events, outputs, metadata,
               uor_address, uor_witness, created_at
        FROM uar_runs
        WHERE run_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """
        pool = await self._get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, run_id)

        if row is None:
            return None

        cols = [
            "run_id", "goal_id", "user_id", "status",
            "skills", "events", "outputs", "metadata",
            "uor_address", "uor_witness", "created_at",
        ]
        record = dict(zip(cols, row, strict=True))
        for key in (
            "skills", "events", "outputs", "metadata", "uor_witness"
        ):
            if isinstance(record[key], str):
                record[key] = json.loads(record[key])
        return record

    def delete(self, run_id: str) -> bool:
        """Remove a single record by run_id."""
        sql = "DELETE FROM uar_runs WHERE run_id = %(run_id)s"
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, {"run_id": run_id})
                deleted = cur.rowcount > 0
            conn.commit()
        finally:
            self._release_conn(conn)
        return deleted

    def purge_old_records(self, retention_days: int) -> int:
        """Remove records older than *retention_days* from PostgreSQL.

        Returns the number of records removed.
        """
        if retention_days <= 0:
            return 0
        import time

        cutoff = time.time() - (retention_days * 86400)
        sql = "DELETE FROM uar_runs WHERE created_at < to_timestamp(%s)"
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (cutoff,))
                removed = cur.rowcount
            conn.commit()
        finally:
            self._release_conn(conn)
        return removed

    # ------------------------------------------------------------------
    # Recommendation feedback (Ω-5.2)
    # ------------------------------------------------------------------

    def record_feedback(
        self,
        recommendation_id: str,
        action: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist operator feedback for a recommendation."""
        self._ensure_feedback_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO uar_recommendation_feedback"
                    " (recommendation_id, action, user_id, created_at)"
                    " VALUES (%s, %s, %s, to_timestamp(%s))",
                    (recommendation_id, action, user_id, time.time()),
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def get_feedback(
        self,
        recommendation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve recommendation feedback entries."""
        self._ensure_feedback_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                if recommendation_id is not None and user_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_feedback"
                        " WHERE recommendation_id = %s AND user_id = %s"
                        " ORDER BY created_at DESC LIMIT %s",
                        (recommendation_id, user_id, limit),
                    )
                elif recommendation_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_feedback"
                        " WHERE recommendation_id = %s"
                        " ORDER BY created_at DESC LIMIT %s",
                        (recommendation_id, limit),
                    )
                elif user_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_feedback"
                        " WHERE user_id = %s"
                        " ORDER BY created_at DESC LIMIT %s",
                        (user_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_feedback"
                        " ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        finally:
            self._release_conn(conn)
        return [dict(zip(cols, r)) for r in rows]

    def _ensure_feedback_table(self) -> None:
        """Create feedback table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_recommendation_feedback (
            id                SERIAL PRIMARY KEY,
            recommendation_id TEXT NOT NULL,
            action            TEXT NOT NULL,
            user_id           TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_rec_id
            ON uar_recommendation_feedback(recommendation_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_user
            ON uar_recommendation_feedback(user_id);
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def record_recommendation_shown(
        self,
        recommendation_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist a shown event for a recommendation."""
        self._ensure_shown_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO uar_recommendation_shown"
                    " (recommendation_id, user_id, shown_at)"
                    " VALUES (%s, %s, to_timestamp(%s))",
                    (recommendation_id, user_id, time.time()),
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def get_shown_recommendations(
        self,
        recommendation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve shown recommendation entries."""
        self._ensure_shown_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                if recommendation_id is not None and user_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_shown"
                        " WHERE recommendation_id = %s AND user_id = %s"
                        " ORDER BY shown_at DESC LIMIT %s",
                        (recommendation_id, user_id, limit),
                    )
                elif recommendation_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_shown"
                        " WHERE recommendation_id = %s"
                        " ORDER BY shown_at DESC LIMIT %s",
                        (recommendation_id, limit),
                    )
                elif user_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_shown"
                        " WHERE user_id = %s"
                        " ORDER BY shown_at DESC LIMIT %s",
                        (user_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_shown"
                        " ORDER BY shown_at DESC LIMIT %s",
                        (limit,),
                    )
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        finally:
            self._release_conn(conn)
        return [dict(zip(cols, r)) for r in rows]

    def _ensure_shown_table(self) -> None:
        """Create shown table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_recommendation_shown (
            id                SERIAL PRIMARY KEY,
            recommendation_id TEXT NOT NULL,
            user_id           TEXT,
            shown_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_shown_rec_id
            ON uar_recommendation_shown(recommendation_id);
        CREATE INDEX IF NOT EXISTS idx_shown_user
            ON uar_recommendation_shown(user_id);
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def record_outcome(
        self, recommendation_id: str, outcome_type: str
    ) -> None:
        """Persist an outcome for a recommendation."""
        self._ensure_outcomes_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO uar_recommendation_outcomes"
                    " (recommendation_id, outcome_type, recorded_at)"
                    " VALUES (%s, %s, to_timestamp(%s))",
                    (recommendation_id, outcome_type, time.time()),
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def get_outcomes(
        self,
        recommendation_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve recommendation outcome entries."""
        self._ensure_outcomes_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                if recommendation_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_outcomes"
                        " WHERE recommendation_id = %s"
                        " ORDER BY recorded_at DESC LIMIT %s",
                        (recommendation_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_outcomes"
                        " ORDER BY recorded_at DESC LIMIT %s",
                        (limit,),
                    )
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        finally:
            self._release_conn(conn)
        return [dict(zip(cols, r)) for r in rows]

    def _ensure_outcomes_table(self) -> None:
        """Create outcomes table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_recommendation_outcomes (
            id                SERIAL PRIMARY KEY,
            recommendation_id TEXT NOT NULL,
            outcome_type      TEXT NOT NULL,
            recorded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_outcomes_rec_id
            ON uar_recommendation_outcomes(recommendation_id);
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def record_recommendation_metadata(
        self,
        recommendation_id: str,
        category: str,
        source: str = "",
        title: str = "",
        confidence: float = 0.0,
        run_id: str = "",
    ) -> None:
        """Store mapping from recommendation_id to metadata."""
        self._ensure_metadata_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO uar_recommendation_metadata"
                    " (recommendation_id, category, source, title,"
                    " confidence, run_id)"
                    " VALUES (%s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (recommendation_id) DO NOTHING",
                    (
                        recommendation_id, category, source,
                        title, confidence, run_id,
                    ),
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def get_recommendation_metadata(
        self,
        recommendation_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve recommendation metadata entries."""
        self._ensure_metadata_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                if recommendation_id is not None:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_metadata"
                        " WHERE recommendation_id = %s LIMIT %s",
                        (recommendation_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM uar_recommendation_metadata"
                        " LIMIT %s",
                        (limit,),
                    )
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        finally:
            self._release_conn(conn)
        return [dict(zip(cols, r)) for r in rows]

    def _ensure_metadata_table(self) -> None:
        """Create metadata table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_recommendation_metadata (
            id                SERIAL PRIMARY KEY,
            recommendation_id TEXT NOT NULL UNIQUE,
            category          TEXT NOT NULL,
            source            TEXT,
            title             TEXT,
            confidence        REAL,
            run_id            TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_meta_rec_id
            ON uar_recommendation_metadata(recommendation_id);
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def _ensure_kv_metadata_table(self) -> None:
        """Create generic key-value metadata table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        finally:
            self._release_conn(conn)

    def put_metadata(self, key: str, value: Any) -> None:
        """Persist a JSON-serialisable value under key."""
        self._ensure_kv_metadata_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO uar_metadata (key, value) VALUES (%s, %s)"
                    " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (key, json.dumps(value)),
                )
            conn.commit()
        finally:
            self._release_conn(conn)

    def get_metadata(self, key: str) -> Optional[Any]:
        """Read a previously stored metadata value, or None."""
        self._ensure_kv_metadata_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM uar_metadata WHERE key = %s",
                    (key,),
                )
                row = cur.fetchone()
        finally:
            self._release_conn(conn)
        if row is None or row[0] is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def list_meta_keys(self) -> List[str]:
        """Return all keys currently stored in metadata."""
        self._ensure_kv_metadata_table()
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT key FROM uar_metadata")
                return [r[0] for r in cur.fetchall()]
        finally:
            self._release_conn(conn)
