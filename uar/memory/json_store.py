import fcntl
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from uar.core.contracts import RunRecord


class JsonRunStore:
    """Append-only JSONL storage for UAR run records with file locking.

    This keeps persistence simple, portable, and easy to inspect before
    introducing SQLite or a distributed event ledger.
    Uses file locking for basic concurrency safety.
    """

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
        """Append record to JSONL file with exclusive lock."""
        with self._thread_lock:
            with self._acquire_lock():
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record), sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

    def list_records(self, user_id: Optional[str] = None) -> List[dict]:
        """List records with shared lock for consistency.

        If user_id is provided, only return records owned by that user.
        """
        if not self.path.exists():
            return []

        with self._thread_lock:
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
                            except json.JSONDecodeError:
                                # Skip corrupted lines
                                continue
                return records
