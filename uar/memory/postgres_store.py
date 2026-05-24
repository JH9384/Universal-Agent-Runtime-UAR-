"""PostgreSQL-backed run store for multi-node UAR deployments.

Uses ``asyncpg`` for async I/O. Falls back to ``psycopg2`` / ``psycopg``
for sync contexts.

Environment:
    UAR_DATABASE_URL — PostgreSQL connection string
        (default: ``postgresql://localhost/uar``)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord

logger = logging.getLogger(__name__)

_PG_AVAILABLE = False
_db_pool: Any = None


def _get_db_url() -> str:
    return os.getenv(
        "UAR_DATABASE_URL",
        "postgresql://localhost/uar",
    )


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
        self._ensure_table()

    def _connect_sync(self):
        """Return a synchronous DBAPI connection."""
        try:
            import psycopg
            return psycopg.connect(self._db_url)
        except ImportError:
            import psycopg2  # type: ignore[import-untyped]
            return psycopg2.connect(self._db_url)

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
            conn.close()

    def append(self, record: RunRecord) -> None:
        """Insert a run record."""
        data = {
            "run_id": getattr(record, "id", ""),
            "goal_id": getattr(record, "goal", {}).get("id", ""),
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
            conn.close()

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

        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()

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
        conn = self._connect_sync()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, {"run_id": run_id})
                row = cur.fetchone()
        finally:
            conn.close()

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
            "run_id": getattr(record, "id", ""),
            "goal_id": getattr(record, "goal", {}).get("id", ""),
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
