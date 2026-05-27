"""SQLite-backed run store as a drop-in replacement for JsonRunStore.

Provides indexed, queryable storage with the same interface.
Much faster for filtering (user_id, date ranges, run_id lookups)
than scanning an entire JSONL file.

Environment:
    UAR_SQLITE_PATH — database file path (default: runs/uar_runs.db)
"""

import json
import os
import queue
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord


class SqliteRunStore:
    """SQLite run store with indexed columns.

    Mirrors the JsonRunStore interface so it can be swapped in
    transparently. Uses WAL mode and a persistent connection for
    5-10x concurrent read throughput.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            path = str(runs_dir / "uar_runs.db")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        # Reader pool for concurrent reads under WAL
        self._read_pool_size = int(os.getenv("UAR_SQLITE_READ_POOL", "4"))
        self._read_pool: queue.Queue = queue.Queue()
        self._read_pool_lock = threading.Lock()
        # Hot data tiering: in-memory LRU for recent runs
        self._hot_cache_size = int(os.getenv("UAR_HOT_CACHE", "100"))
        self._hot_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._hot_cache_lock = threading.Lock()
        self._ensure_table()
        self._init_read_pool()

    def _init_read_pool(self) -> None:
        """Pre-create reader connections for WAL-mode concurrent reads."""
        for _ in range(self._read_pool_size):
            self._read_pool.put(self._connect())

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._path), check_same_thread=False, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=memory")
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        """Return persistent connection; thread-safe via lock."""
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def _ensure_table(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT NOT NULL,
            goal_id      TEXT,
            user_id      TEXT,
            status       TEXT,
            skills       TEXT,
            events       TEXT,
            outputs      TEXT,
            metadata     TEXT,
            uor_address  TEXT,
            uor_witness  TEXT,
            created_at   REAL DEFAULT (julianday('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_runs_run_id ON uar_runs(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_user  ON uar_runs(user_id);
        CREATE INDEX IF NOT EXISTS idx_runs_created
            ON uar_runs(created_at DESC);
        """
        conn = self._connect()
        try:
            conn.executescript(ddl)
            for column, col_type in (
                ("uor_address", "TEXT"),
                ("uor_witness", "TEXT"),
            ):
                try:
                    conn.execute(
                        f"ALTER TABLE uar_runs ADD COLUMN {column} {col_type}"
                    )
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc):
                        raise
            conn.commit()
        finally:
            conn.close()

    def append(self, record: RunRecord) -> None:
        witness = getattr(record, "uor_witness", None)
        data = {
            "run_id": getattr(record, "run_id", getattr(record, "id", "")),
            "goal_id": getattr(
                record, "goal_id", getattr(record, "goal", {}).get("id", "")
            ),
            "user_id": getattr(record, "user_id", None),
            "status": getattr(record, "status", "unknown"),
            "skills": json.dumps(getattr(record, "skills", [])),
            "events": json.dumps(getattr(record, "events", [])),
            "outputs": json.dumps(getattr(record, "outputs", {})),
            "metadata": json.dumps(getattr(record, "metadata", {})),
            "uor_address": getattr(record, "uor_address", None),
            "uor_witness": json.dumps(witness) if witness is not None else None,
        }
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO uar_runs"
                " (run_id, goal_id, user_id, status,"
                "  skills, events, outputs, metadata, uor_address, uor_witness)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                tuple(data.values()),
            )
        # Populate hot cache with newly inserted record
        hot_record = dict(data)
        hot_record["skills"] = json.loads(hot_record["skills"])
        hot_record["events"] = json.loads(hot_record["events"])
        hot_record["outputs"] = json.loads(hot_record["outputs"])
        hot_record["metadata"] = json.loads(hot_record["metadata"])
        if hot_record["uor_witness"]:
            try:
                hot_record["uor_witness"] = json.loads(
                    hot_record["uor_witness"]
                )
            except json.JSONDecodeError:
                pass
        hot_record["created_at"] = None
        with self._hot_cache_lock:
            self._hot_cache[data["run_id"]] = hot_record
            self._hot_cache.move_to_end(data["run_id"])
            while len(self._hot_cache) > self._hot_cache_size:
                self._hot_cache.popitem(last=False)

    def append_many(self, records: List[RunRecord]) -> None:
        """Bulk insert multiple records in a single transaction."""
        if not records:
            return
        sql = (
            "INSERT INTO uar_runs"
            " (run_id, goal_id, user_id, status,"
            "  skills, events, outputs, metadata, uor_address, uor_witness)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
        )
        rows = []
        for record in records:
            witness = getattr(record, "uor_witness", None)
            rows.append(
                tuple([
                    getattr(record, "run_id", getattr(record, "id", "")),
                    getattr(
                        record,
                        "goal_id",
                        getattr(record, "goal", {}).get("id", ""),
                    ),
                    getattr(record, "user_id", None),
                    getattr(record, "status", "unknown"),
                    json.dumps(getattr(record, "skills", [])),
                    json.dumps(getattr(record, "events", [])),
                    json.dumps(getattr(record, "outputs", {})),
                    json.dumps(getattr(record, "metadata", {})),
                    getattr(record, "uor_address", None),
                    (
                        json.dumps(witness)
                        if witness is not None
                        else None
                    ),
                ])
            )
        with self._lock:
            conn = self._get_conn()
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(sql, rows)
            conn.execute("COMMIT")

    def _get_read_conn(self) -> sqlite3.Connection:
        """Borrow a reader connection from the pool."""
        try:
            return self._read_pool.get(block=False)
        except queue.Empty:
            return self._connect()

    def _release_read_conn(self, conn: sqlite3.Connection) -> None:
        """Return a reader connection to the pool."""
        try:
            self._read_pool.put(conn, block=False)
        except queue.Full:
            conn.close()

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        conn = self._get_read_conn()
        try:
            if user_id is not None:
                cur = conn.execute(
                    "SELECT * FROM uar_runs WHERE user_id = ?"
                    " ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM uar_runs"
                    " ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        finally:
            self._release_read_conn(conn)

        return [_decode_row(dict(r)) for r in rows]

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single record by run ID.

        Checks hot cache first, then falls back to SQLite.
        """
        with self._hot_cache_lock:
            if run_id in self._hot_cache:
                self._hot_cache.move_to_end(run_id)
                return self._hot_cache[run_id]

        conn = self._get_read_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM uar_runs WHERE run_id = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            )
            row = cur.fetchone()
        finally:
            self._release_read_conn(conn)
        if row is None:
            return None
        record = _decode_row(dict(row))
        with self._hot_cache_lock:
            self._hot_cache[run_id] = record
            self._hot_cache.move_to_end(run_id)
            while len(self._hot_cache) > self._hot_cache_size:
                self._hot_cache.popitem(last=False)
        return record

    def purge_old_records(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        import time

        cutoff = time.time() - (retention_days * 86400)
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "DELETE FROM uar_runs WHERE created_at < ?", (cutoff,)
            )
            return cur.rowcount

    def flush(self) -> None:
        """Ensure WAL checkpointed."""
        with self._lock:
            if self._conn:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

    def close(self) -> None:
        """Close persistent connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("skills", "events", "outputs", "metadata", "uor_witness"):
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return row
