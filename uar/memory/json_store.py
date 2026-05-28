import fcntl
import json
import logging
import os
import shutil
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from uar.core.contracts import RunRecord

logger = logging.getLogger(__name__)


class JsonRunStore:
    """Append-only JSONL storage for UAR run records with file locking.

    This keeps persistence simple, portable, and easy to inspect before
    introducing SQLite or a distributed event ledger.
    Uses file locking for basic concurrency safety.
    """

    _BATCH_SIZE = max(
        1, int(os.getenv("UAR_JSON_BATCH_SIZE", "1").strip() or "1")
    )

    def __init__(self, path: Optional[str] = None):
        # Use absolute path from environment or default to runs/ in project root  # noqa: E501
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            default_path = runs_dir / "uar_runs.jsonl"
            path = str(default_path)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.path.parent / ".uar_lock"
        self._thread_lock = threading.Lock()
        self._buffer: List[str] = []

    @contextmanager
    def _acquire_lock(self, shared: bool = False):
        """Acquire file lock for read or write operations with context manager."""  # noqa: E501
        self._lock_file.touch(exist_ok=True)
        lock_fd = open(self._lock_file, "w")
        try:
            fcntl.flock(
                lock_fd.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            )
            yield lock_fd
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()

    def append(self, record: RunRecord) -> None:
        """Buffer record; flush to JSONL file when batch size reached."""
        data = asdict(record)
        data["created_at"] = time.time()
        line = json.dumps(data, sort_keys=True) + "\n"
        with self._thread_lock:
            self._buffer.append(line)
            if len(self._buffer) >= self._BATCH_SIZE:
                self._flush()

    def _flush(self) -> None:
        """Write buffered records to disk with exclusive lock."""
        if not self._buffer:
            return
        with self._acquire_lock():
            with self.path.open("a", encoding="utf-8") as f:
                f.writelines(self._buffer)
                f.flush()
                os.fsync(f.fileno())
        self._buffer.clear()

    def flush(self) -> None:
        """Public flush for explicit buffer draining."""
        with self._thread_lock:
            self._flush()

    def __del__(self):
        """Ensure buffered records are written before GC."""
        try:
            self.flush()
        except Exception:
            logger.warning("JsonRunStore flush failed", exc_info=True)

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[dict]:
        """List records with shared lock for consistency.

        If user_id is provided, only return records owned by that user.
        """
        if not self.path.exists():
            return []

        with self._thread_lock:
            self._flush()
            with self._acquire_lock(shared=True):
                records = []
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                record = json.loads(line)
                                owner = record.get("user_id")
                                if user_id is None or owner == user_id:
                                    records.append(record)
                                    if len(records) >= limit:
                                        break
                            except json.JSONDecodeError:
                                # Skip corrupted lines
                                continue
                return records

    def list_all(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[dict]:
        """Alias for list_records — returns all stored run records."""
        return self.list_records(user_id=user_id, limit=limit)

    def get_by_run_id(self, run_id: str) -> Optional[dict]:
        """Fetch a single record by run ID.

        Scans from newest to oldest so the most recent record wins.
        """
        records = self.list_records()
        for record in reversed(records):
            if record.get("run_id") == run_id:
                return record
        return None

    def delete(self, run_id: str) -> bool:
        """Remove a single record by run_id from the JSONL file.

        Returns True if a record was removed, False otherwise.
        """
        if not self.path.exists():
            return False

        removed = False
        kept_lines: List[str] = []

        with self._thread_lock:
            self._flush()
            with self._acquire_lock():
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            record = json.loads(raw)
                            if record.get("run_id") == run_id:
                                removed = True
                                continue
                        except json.JSONDecodeError:
                            pass
                        kept_lines.append(raw)

                if removed:
                    tmp = self.path.with_suffix(".jsonl.tmp")
                    with tmp.open("w", encoding="utf-8") as f:
                        for raw in kept_lines:
                            f.write(raw + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                    try:
                        tmp.replace(self.path)
                    except PermissionError:
                        shutil.copy2(str(tmp), str(self.path))
                        tmp.unlink()
        return removed

    def purge_old_records(self, retention_days: int) -> int:
        """Remove records older than *retention_days* from the JSONL file.

        Returns the number of records removed.
        """
        if retention_days <= 0 or not self.path.exists():
            return 0

        cutoff = time.time() - (retention_days * 86400)
        removed = 0
        kept_lines: List[str] = []

        with self._thread_lock:
            self._flush()
            with self._acquire_lock():
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            record = json.loads(raw)
                            ts = record.get("created_at")
                            if ts and isinstance(ts, (int, float)):
                                if ts < cutoff:
                                    removed += 1
                                    continue
                        except json.JSONDecodeError:
                            # Keep corrupted lines rather than losing data
                            pass
                        kept_lines.append(raw)

                # Rewrite only if we removed something
                if removed > 0:
                    tmp = self.path.with_suffix(".jsonl.tmp")
                    with tmp.open("w", encoding="utf-8") as f:
                        for raw in kept_lines:
                            f.write(raw + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                    try:
                        tmp.replace(self.path)
                    except PermissionError:
                        # Windows: cannot replace if file is open; fallback
                        shutil.copy2(str(tmp), str(self.path))
                        tmp.unlink()

        return removed
