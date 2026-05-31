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
    transparently. Uses WAL mode, a reader pool for concurrent
    reads, and a dedicated writer thread for serialized writes.
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
        self._read_pool_size = max(
            1,
            int(os.getenv("UAR_SQLITE_READ_POOL", "4").strip() or "4"),
        )
        self._read_pool: queue.Queue = queue.Queue()
        self._read_pool_lock = threading.Lock()
        # Hot data tiering: in-memory LRU for recent runs
        self._hot_cache_size = max(
            1,
            int(os.getenv("UAR_HOT_CACHE", "100").strip() or "100"),
        )
        self._hot_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._hot_cache_lock = threading.Lock()
        # Writer thread for serialized writes
        self._writer_queue: queue.Queue = queue.Queue(
            maxsize=max(
                1,
                int(
                    os.getenv("UAR_SQLITE_WRITER_QUEUE_SIZE", "1000").strip()
                    or "1000"
                ),
            )
        )
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_shutdown = threading.Event()
        self._writer_exception: Optional[Exception] = None
        self._ensure_table()
        self._init_read_pool()
        self._start_writer()

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

    # ------------------------------------------------------------------
    # Writer thread
    # ------------------------------------------------------------------

    def _start_writer(self) -> None:
        """Start the background writer thread."""
        if self._writer_thread is not None:
            return
        self._writer_shutdown.clear()
        self._writer_exception = None
        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True
        )
        self._writer_thread.start()

    def _writer_loop(self) -> None:
        """Background thread that serializes all write operations."""
        conn = self._connect()
        try:
            while not self._writer_shutdown.is_set():
                try:
                    item = self._writer_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if item is None:  # sentinel
                    break
                # Distinguish async (2-tuple) vs sync (4-tuple) items
                if len(item) == 4:
                    op, payload, result_container, event = item
                else:
                    op, payload = item
                    result_container = None
                    event = None
                result: Any = None
                try:
                    if op == "insert":
                        conn.execute(
                            "INSERT INTO uar_runs"
                            " (run_id, goal_id, user_id, status,"
                            "  skills, events, outputs, metadata,"
                            "  uor_address, uor_witness, created_at)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            payload,
                        )
                    elif op == "upsert":
                        conn.execute(
                            "INSERT INTO uar_runs"
                            " (run_id, goal_id, user_id, status,"
                            "  skills, events, outputs, metadata,"
                            "  uor_address, uor_witness, created_at)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?)"
                            " ON CONFLICT(run_id) DO UPDATE SET"
                            "  goal_id=excluded.goal_id,"
                            "  user_id=excluded.user_id,"
                            "  status=excluded.status,"
                            "  skills=excluded.skills,"
                            "  events=excluded.events,"
                            "  outputs=excluded.outputs,"
                            "  metadata=excluded.metadata,"
                            "  uor_address=excluded.uor_address,"
                            "  uor_witness=excluded.uor_witness,"
                            "  created_at=excluded.created_at",
                            payload,
                        )
                    elif op == "delete":
                        cur = conn.execute(
                            "DELETE FROM uar_runs WHERE run_id = ?",
                            (payload,),
                        )
                        result = cur.rowcount
                    elif op == "purge":
                        cur = conn.execute(
                            "DELETE FROM uar_runs WHERE CASE"
                            " WHEN created_at > 1000000000"
                            " THEN datetime(created_at, 'unixepoch')"
                            " ELSE datetime(created_at) END"
                            " < datetime(?, 'unixepoch')",
                            (payload,),
                        )
                        result = cur.rowcount
                    elif op == "checkpoint":
                        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception as exc:
                    self._writer_exception = exc
                    result = exc
                finally:
                    if result_container is not None:
                        result_container[0] = result
                    if event is not None:
                        event.set()
                    self._writer_queue.task_done()
        finally:
            conn.close()

    def _enqueue_write(self, op: str, payload: Any) -> None:
        """Enqueue a write operation for the background writer thread."""
        if self._writer_exception is not None:
            raise self._writer_exception
        self._writer_queue.put((op, payload), block=True)

    def _enqueue_write_sync(self, op: str, payload: Any) -> Any:
        """Enqueue a write and block until it completes, returning result."""
        if self._writer_exception is not None:
            raise self._writer_exception
        result_container: List[Any] = [None]
        event = threading.Event()
        self._writer_queue.put((op, payload, result_container, event))
        event.wait(timeout=10.0)
        return result_container[0]

    def _drain_writer(self, timeout: float = 5.0) -> None:
        """Wait until the writer queue is empty."""
        self._writer_queue.join()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS uar_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT NOT NULL UNIQUE,
            goal_id      TEXT,
            user_id      TEXT,
            status       TEXT,
            skills       TEXT,
            events       TEXT,
            outputs      TEXT,
            metadata     TEXT,
            uor_address  TEXT,
            uor_witness  TEXT,
            created_at   REAL DEFAULT (strftime('%s', 'now'))
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

    # ------------------------------------------------------------------
    # Write interface (non-blocking enqueue)
    # ------------------------------------------------------------------

    def append(self, record: RunRecord) -> None:
        import time as _time

        witness = getattr(record, "uor_witness", None)
        payload = (
            getattr(record, "run_id", getattr(record, "id", "")),
            getattr(
                record, "goal_id", getattr(record, "goal", {}).get("id", "")
            ),
            getattr(record, "user_id", None),
            getattr(record, "status", "unknown"),
            json.dumps(getattr(record, "skills", [])),
            json.dumps(getattr(record, "events", [])),
            json.dumps(getattr(record, "outputs", {})),
            json.dumps(getattr(record, "metadata", {})),
            getattr(record, "uor_address", None),
            json.dumps(witness) if witness is not None else None,
            _time.time(),
        )
        self._enqueue_write("insert", payload)
        # Populate hot cache with newly inserted record
        hot_record = {
            "run_id": payload[0],
            "goal_id": payload[1],
            "user_id": payload[2],
            "status": payload[3],
            "skills": json.loads(payload[4]),
            "events": json.loads(payload[5]),
            "outputs": json.loads(payload[6]),
            "metadata": json.loads(payload[7]),
            "uor_address": payload[8],
            "uor_witness": (
                json.loads(payload[9]) if payload[9] is not None else None
            ),
            "created_at": payload[10],
        }
        with self._hot_cache_lock:
            self._hot_cache[hot_record["run_id"]] = hot_record
            self._hot_cache.move_to_end(hot_record["run_id"])
            while len(self._hot_cache) > self._hot_cache_size:
                self._hot_cache.popitem(last=False)

    def append_many(self, records: List[RunRecord]) -> None:
        """Bulk insert multiple records via the writer queue."""
        if not records:
            return
        import time as _time

        for record in records:
            witness = getattr(record, "uor_witness", None)
            payload = (
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
                json.dumps(witness) if witness is not None else None,
                _time.time(),
            )
            self._enqueue_write("insert", payload)

    # ------------------------------------------------------------------
    # Read interface (unchanged)
    # ------------------------------------------------------------------

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

    def list_all(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Alias for list_records — satisfies RunStoreProtocol."""
        return self.list_records(user_id=user_id, limit=limit)

    # ------------------------------------------------------------------
    # Delete / purge (enqueue via writer)
    # ------------------------------------------------------------------

    def delete(self, run_id: str) -> bool:
        """Remove a single record by run_id."""
        rowcount = self._enqueue_write_sync("delete", run_id)
        with self._hot_cache_lock:
            self._hot_cache.pop(run_id, None)
        return bool(rowcount and rowcount > 0)

    def purge_old_records(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        import time

        cutoff = time.time() - (retention_days * 86400)
        rowcount = self._enqueue_write_sync("purge", cutoff)
        return rowcount if isinstance(rowcount, int) else 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Drain the writer queue and checkpoint WAL."""
        self._drain_writer()
        self._enqueue_write("checkpoint", None)

    def close(self) -> None:
        """Signal writer thread to stop, drain queue, close connections."""
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_shutdown.set()
            # Sentinel to unblock writer thread
            try:
                self._writer_queue.put(None, block=False)
            except queue.Full:
                pass
            self._writer_thread.join(timeout=5.0)
        # Drain and close all reader pool connections
        with self._read_pool_lock:
            while not self._read_pool.empty():
                try:
                    conn = self._read_pool.get(block=False)
                    conn.close()
                except queue.Empty:
                    break
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
