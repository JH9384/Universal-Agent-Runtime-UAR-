"""SQLite-backed run store as a drop-in replacement for JsonRunStore.

Provides indexed, queryable storage with the same interface.
Much faster for filtering (user_id, date ranges, run_id lookups)
than scanning an entire JSONL file.

Environment:
    UAR_SQLITE_PATH — database file path (default: runs/uar_runs.db)
"""

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord


class SqliteRunStore:
    """SQLite run store with indexed columns.

    Mirrors the JsonRunStore interface so it can be swapped in
    transparently.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            path = str(runs_dir / "uar_runs.db")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_runs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id     TEXT NOT NULL,
            goal_id    TEXT,
            user_id    TEXT,
            status     TEXT,
            skills     TEXT,
            events     TEXT,
            outputs    TEXT,
            metadata   TEXT,
            created_at REAL DEFAULT (julianday('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_runs_run_id ON uar_runs(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_user  ON uar_runs(user_id);
        CREATE INDEX IF NOT EXISTS idx_runs_created
            ON uar_runs(created_at DESC);
        """
        conn = self._connect()
        try:
            conn.executescript(ddl)
            conn.commit()
        finally:
            conn.close()

    def append(self, record: RunRecord) -> None:
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
        INSERT INTO uar_runs
            (run_id, goal_id, user_id, status,
             skills, events, outputs, metadata)
        VALUES
            (:run_id, :goal_id, :user_id, :status,
             :skills, :events, :outputs, :metadata)
        """
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(sql, data)
                conn.commit()
            finally:
                conn.close()

    def append_many(self, records: List[RunRecord]) -> None:
        """Bulk insert multiple records in a single transaction."""
        if not records:
            return
        sql = """
        INSERT INTO uar_runs
            (run_id, goal_id, user_id, status,
             skills, events, outputs, metadata)
        VALUES
            (:run_id, :goal_id, :user_id, :status,
             :skills, :events, :outputs, :metadata)
        """
        rows = []
        for record in records:
            rows.append({
                "run_id": getattr(record, "id", ""),
                "goal_id": getattr(record, "goal", {}).get("id", ""),
                "user_id": getattr(record, "user_id", None),
                "status": getattr(record, "status", "unknown"),
                "skills": json.dumps(getattr(record, "skills", [])),
                "events": json.dumps(getattr(record, "events", [])),
                "outputs": json.dumps(getattr(record, "outputs", {})),
                "metadata": json.dumps(getattr(record, "metadata", {})),
            })
        with self._lock:
            conn = self._connect()
            try:
                conn.executemany(sql, rows)
                conn.commit()
            finally:
                conn.close()

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM uar_runs"
        params: List[Any] = []
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params.append(user_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params)
                rows = cur.fetchall()
            finally:
                conn.close()

        return [_decode_row(dict(r)) for r in rows]

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        sql = (
            "SELECT * FROM uar_runs WHERE run_id = ?"
            " ORDER BY created_at DESC LIMIT 1"
        )
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, (run_id,))
                row = cur.fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return _decode_row(dict(row))

    def purge_old_records(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        import time

        cutoff = time.time() - (retention_days * 86400)
        sql = "DELETE FROM uar_runs WHERE created_at < ?"
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, (cutoff,))
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()

    def flush(self) -> None:
        """No-op; SQLite is immediate."""


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("skills", "events", "outputs", "metadata"):
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return row
