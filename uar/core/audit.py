"""Structured audit logging for compliance (SOC2, GDPR).

Writes immutable JSONL records to a dedicated file separate from
application logs. Each record captures who, what, when, and the
outcome of API interactions.

T3 — Immutable Audit Logs:
- Hash-chain linking for tamper evidence (SHA-256)
- Optional S3 shipping (boto3, soft dependency)
- Optional CloudWatch shipping (boto3, soft dependency)
- Verify endpoint detects chain breaks
"""

import fcntl
import hashlib
import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from uar.core.json_utils import maybe_rotate_jsonl

logger = logging.getLogger(__name__)


class AuditLogger:
    """Thread-safe JSONL audit log with file locking and hash chain.

    Records are append-only and immutable. Each record links to the
    previous record via a SHA-256 hash, forming a tamper-evident chain.
    """

    _MAX_FILE_SIZE_MB = max(
        1, int(os.getenv("UAR_AUDIT_MAX_SIZE_MB", "100").strip() or "100")
    )
    _MAX_BACKUPS = max(
        1, int(os.getenv("UAR_AUDIT_MAX_BACKUPS", "5").strip() or "5")
    )

    def __init__(self, path: Optional[str] = None):
        if path is None:
            runs_dir = Path(os.getenv("RUNS_DIR", "runs")).resolve()
            default_path = runs_dir / "uar_audit.jsonl"
            path = str(default_path)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.path.parent / ".uar_audit_lock"
        self._thread_lock = threading.Lock()
        # Optional external sinks
        self._s3_bucket = os.getenv("UAR_AUDIT_S3_BUCKET", "").strip()
        self._cw_group = os.getenv("UAR_AUDIT_CLOUDWATCH_GROUP", "").strip()
        self._cw_stream = os.getenv(
            "UAR_AUDIT_CLOUDWATCH_STREAM", "uar-audit"
        ).strip()

    # ------------------------------------------------------------------
    # Hash chain helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(record: Dict[str, Any]) -> str:
        """Return SHA-256 of the canonical JSON of *record*."""
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _compute_uor_digest(record: Dict[str, Any]) -> Optional[str]:
        """Return UOR-ADDR-1 canonical digest of *record*.

        Provides a portable, cross-system content address aligned with
        UOR Foundation standards (RFC8785 JCS canonicalization).
        """
        try:
            from uar.uor.bounded_json import compute_uor_digest

            return compute_uor_digest(record)
        except Exception:
            return None

    def _get_last_hash(self) -> str:
        """Return the hash of the last record in the file, or '' if empty."""
        if not self.path.exists():
            return ""
        last_line = ""
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if not last_line:
            return ""
        try:
            rec = json.loads(last_line)
            return rec.get("hash", "")
        except json.JSONDecodeError:
            return ""

    # ------------------------------------------------------------------
    # External sinks (soft dependencies)
    # ------------------------------------------------------------------

    def _ship_to_s3(self, line: str) -> None:
        if not self._s3_bucket:
            return
        try:
            import boto3

            key = (
                f"uar-audit/{time.strftime('%Y/%m/%d')}/"
                f"{time.time():.6f}.jsonl"
            )
            boto3.client("s3").put_object(
                Bucket=self._s3_bucket,
                Key=key,
                Body=line.encode("utf-8"),
            )
        except Exception:
            logger.debug("S3 audit ship failed", exc_info=True)

    def _ship_to_cloudwatch(self, record: Dict[str, Any]) -> None:
        if not self._cw_group:
            return
        try:
            import boto3

            boto3.client("logs").put_log_events(
                logGroupName=self._cw_group,
                logStreamName=self._cw_stream,
                logEvents=[
                    {
                        "timestamp": int(
                            record.get("unix_time", time.time()) * 1000
                        ),
                        "message": json.dumps(record, sort_keys=True),
                    }
                ],
            )
        except Exception:
            logger.debug("CloudWatch audit ship failed", exc_info=True)

    # ------------------------------------------------------------------
    # Rotation & locking
    # ------------------------------------------------------------------

    def _maybe_rotate(self) -> None:
        """Rotate the audit file if it exceeds the size limit."""
        maybe_rotate_jsonl(
            self.path,
            max_size_mb=self._MAX_FILE_SIZE_MB,
            max_backups=self._MAX_BACKUPS,
        )

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        prev_hash = self._get_last_hash()
        record: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "unix_time": time.time(),
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource": resource,
            "outcome": outcome,
            "prev_hash": prev_hash,
        }
        if details:
            record["details"] = details
        if request_id:
            record["request_id"] = request_id
        if client_ip:
            record["client_ip"] = client_ip

        # Compute own hash after all fields are set
        record["hash"] = self._compute_hash(record)

        # UOR canonical digest (portable content address)
        uor_digest = self._compute_uor_digest(record)
        if uor_digest:
            record["uor_digest"] = uor_digest

        line = json.dumps(record, sort_keys=True) + "\n"

        with self._thread_lock:
            with self._acquire_lock():
                self._maybe_rotate()
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())

        # Ship to external sinks outside the file lock
        self._ship_to_s3(line)
        self._ship_to_cloudwatch(record)

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

    def verify_chain(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """Verify the hash chain integrity.

        Returns:
            (ok, failures) where *failures* lists every record whose
            ``prev_hash`` does not match the actual hash of the
            preceding record, or whose own ``hash`` is incorrect.
        """
        if not self.path.exists():
            return True, []

        failures: list[Dict[str, Any]] = []
        prev_hash = ""
        with self.path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    failures.append(
                        {
                            "line": lineno,
                            "error": "json_decode",
                            "record": None,
                        }
                    )
                    continue

                # Check prev_hash linkage
                if rec.get("prev_hash", "") != prev_hash:
                    failures.append(
                        {
                            "line": lineno,
                            "error": "prev_hash_mismatch",
                            "expected_prev_hash": prev_hash,
                            "actual_prev_hash": rec.get("prev_hash", ""),
                            "record": rec,
                        }
                    )

                # Check own hash
                stored_hash = rec.pop("hash", "")
                # uor_digest is added after hash computation; exclude it
                # from verification so existing records remain valid.
                rec.pop("uor_digest", None)
                computed = self._compute_hash(rec)
                rec["hash"] = stored_hash  # restore
                if stored_hash != computed:
                    failures.append(
                        {
                            "line": lineno,
                            "error": "hash_mismatch",
                            "expected_hash": computed,
                            "actual_hash": stored_hash,
                            "record": rec,
                        }
                    )

                prev_hash = stored_hash

        return len(failures) == 0, failures


# Module-level singleton — created lazily on first use
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Return the shared AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
