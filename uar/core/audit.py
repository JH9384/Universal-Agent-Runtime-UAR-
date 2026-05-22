"""Structured audit logging for compliance (SOC2, GDPR).

Writes immutable JSONL records to a dedicated file separate from
application logs. Each record captures who, what, when, and the
outcome of API interactions.
"""

import fcntl
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional


class AuditLogger:
    """Thread-safe JSONL audit log with file locking.

    Records are append-only and immutable. The file can be shipped
    to a SIEM or cloud watch using standard log forwarders.
    """

    def __init__(self, path: Optional[str] = None):
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            default_path = runs_dir / "uar_audit.jsonl"
            path = str(default_path)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.path.parent / ".uar_audit_lock"
        self._thread_lock = threading.Lock()

    @contextmanager
    def _acquire_lock(self):
        """Acquire exclusive file lock for writing."""
        self._lock_file.touch(exist_ok=True)
        lock_fd = open(self._lock_file, "w")
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            yield lock_fd
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()

    def write(
        self,
        *,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        """Append a single audit record.

        Args:
            event_type: Category e.g. "api_access", "auth",
            actor: Who performed the action
                (user ID, service name, "anonymous")
            action: What was done (HTTP method or verb)
            resource: What was affected (URL path or object ID)
            outcome: "success", "failure", "denied", "error"
            details: Optional extra context (safe, non-PII)
            request_id: Correlation/request ID
            client_ip: Source IP address
        """
        record: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "unix_time": time.time(),
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource": resource,
            "outcome": outcome,
        }
        if details:
            record["details"] = details
        if request_id:
            record["request_id"] = request_id
        if client_ip:
            record["client_ip"] = client_ip

        with self._thread_lock:
            with self._acquire_lock():
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

    def list_records(
        self, event_type: Optional[str] = None, limit: int = 1000
    ) -> list[Dict[str, Any]]:
        """Read records (for local inspection/testing only).

        Not for production querying — ship to a SIEM instead.
        """
        if not self.path.exists():
            return []

        records: list[Dict[str, Any]] = []
        with self._thread_lock:
            with self._acquire_lock():
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            if event_type is None:
                                records.append(rec)
                            elif rec.get("event_type") == event_type:
                                records.append(rec)
                            if len(records) >= limit:
                                break
                        except json.JSONDecodeError:
                            continue
        return records


# Module-level singleton — created lazily on first use
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Return the shared AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
