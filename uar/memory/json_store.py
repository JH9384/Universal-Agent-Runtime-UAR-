import fcntl
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import List

from uar.core.contracts import RunRecord


class JsonRunStore:
    """Append-only JSONL storage for UAR run records with file locking.

    This keeps persistence simple, portable, and easy to inspect before
    introducing SQLite or a distributed event ledger.
    Uses file locking for basic concurrency safety.
    """

    def __init__(self, path: str = None):
        # Use absolute path from environment or default to runs/ in project root
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            path = runs_dir / "uar_runs.jsonl"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.path.parent / ".uar_lock"

    def _acquire_lock(self):
        """Acquire exclusive file lock for write operations."""
        self._lock_file.touch(exist_ok=True)
        self._lock_fd = open(self._lock_file, "w")
        fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX)

    def _release_lock(self):
        """Release file lock."""
        if hasattr(self, '_lock_fd'):
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()

    def append(self, record: RunRecord) -> None:
        """Append record to JSONL file with exclusive lock."""
        self._acquire_lock()
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record), sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        finally:
            self._release_lock()

    def list_records(self) -> List[dict]:
        """List all records with shared lock for consistency."""
        if not self.path.exists():
            return []

        self._acquire_lock()
        try:
            records = []
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Skip corrupted lines
                            continue
            return records
        finally:
            self._release_lock()
