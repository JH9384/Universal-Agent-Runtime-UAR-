"""Tests for structured audit logging.

Covers AuditLogger write and read operations.
"""

import json
import os
import tempfile
from unittest.mock import patch

from uar.core.audit import AuditLogger, get_audit_logger


class TestAuditLoggerInit:
    """Initialization."""

    def test_default_path(self):
        with patch.dict("os.environ", {"RUNS_DIR": "/tmp/test_runs"}):
            logger = AuditLogger()
        assert logger.path.name == "uar_audit.jsonl"

    def test_custom_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            assert str(logger.path) == path


class TestAuditLoggerWrite:
    """Writing audit records."""

    def test_write_basic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="api_access",
                actor="user_1",
                action="GET",
                resource="/api/v1/runs",
                outcome="success",
            )
            assert os.path.exists(path)
            with open(path) as f:
                record = json.loads(f.readline())
            assert record["event_type"] == "api_access"
            assert record["actor"] == "user_1"
            assert record["outcome"] == "success"
            assert "timestamp" in record
            assert "unix_time" in record

    def test_write_with_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="auth",
                actor="user_1",
                action="login",
                resource="/auth",
                outcome="success",
                details={"method": "password"},
                request_id="req-123",
                client_ip="127.0.0.1",
            )
            with open(path) as f:
                record = json.loads(f.readline())
            assert record["details"] == {"method": "password"}
            assert record["request_id"] == "req-123"
            assert record["client_ip"] == "127.0.0.1"

    def test_write_no_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="test",
                actor="system",
                action="check",
                resource="/health",
                outcome="success",
            )
            with open(path) as f:
                record = json.loads(f.readline())
            assert "details" not in record
            assert "request_id" not in record

    def test_write_calls_fsync(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            with patch("os.fsync") as mock_fsync:
                logger.write(
                    event_type="test",
                    actor="system",
                    action="check",
                    resource="/health",
                    outcome="success",
                )
            mock_fsync.assert_called_once()


class TestAuditLoggerList:
    """Reading audit records."""

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="type_a", actor="a", action="GET",
                resource="/", outcome="success",
            )
            logger.write(
                event_type="type_b", actor="b", action="POST",
                resource="/", outcome="success",
            )
            records = logger.list_records()
            assert len(records) == 2

    def test_list_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="type_a", actor="a", action="GET",
                resource="/", outcome="success",
            )
            logger.write(
                event_type="type_b", actor="b", action="POST",
                resource="/", outcome="success",
            )
            records = logger.list_records(event_type="type_a")
            assert len(records) == 1
            assert records[0]["event_type"] == "type_a"

    def test_list_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            for i in range(5):
                logger.write(
                    event_type="test", actor="a", action="GET",
                    resource="/", outcome="success",
                )
            records = logger.list_records(limit=3)
            assert len(records) == 3

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            records = logger.list_records()
            assert records == []

    def test_list_corrupted_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            with open(path, "w") as f:
                f.write("not json\n")
                f.write('{"event_type": "ok"}\n')
            logger = AuditLogger(path=path)
            records = logger.list_records()
            assert len(records) == 1
            assert records[0]["event_type"] == "ok"

    def test_list_empty_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            with open(path, "w") as f:
                f.write('{"event_type": "ok"}\n')
                f.write("\n")
                f.write('{"event_type": "ok2"}\n')
            logger = AuditLogger(path=path)
            records = logger.list_records()
            assert len(records) == 2


class TestAuditUORDigest:
    """UOR canonical digest on audit records."""

    def test_uor_digest_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="api_access",
                actor="user_1",
                action="GET",
                resource="/api/v1/runs",
                outcome="success",
            )
            with open(path) as f:
                record = json.loads(f.readline())
            assert "uor_digest" in record
            assert record["uor_digest"].startswith("sha256:")

    def test_verify_chain_ignores_uor_digest(self):
        """Hash verification must succeed even with uor_digest present."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            logger.write(
                event_type="test", actor="a", action="GET",
                resource="/", outcome="success",
            )
            ok, failures = logger.verify_chain()
            assert ok is True
            assert failures == []


class TestGetAuditLogger:
    """Singleton accessor."""

    def test_singleton(self):
        with patch.dict("os.environ", {"RUNS_DIR": "/tmp/test_runs2"}):
            logger1 = get_audit_logger()
            logger2 = get_audit_logger()
            assert logger1 is logger2


# --- Rotation tests ---


class TestAuditLoggerRotation:
    def test_rotation_creates_backup(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            monkeypatch.setattr(logger, "_MAX_FILE_SIZE_MB", 1)
            # Write enough data to exceed 1MB (~150 bytes per record * 7000)
            for _ in range(8000):
                logger.write(
                    event_type="test", actor="a", action="GET",
                    resource="/", outcome="success",
                )
            assert logger.path.exists()
            backup = logger.path.with_suffix(".jsonl.1")
            assert backup.exists()

    def test_rotation_respects_max_backups(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            monkeypatch.setattr(logger, "_MAX_FILE_SIZE_MB", 1)
            monkeypatch.setattr(logger, "_MAX_BACKUPS", 2)
            for _ in range(3):
                for _ in range(8000):
                    logger.write(
                        event_type="test", actor="a", action="GET",
                        resource="/", outcome="success",
                    )
            assert logger.path.with_suffix(".jsonl.1").exists()
            assert logger.path.with_suffix(".jsonl.2").exists()
            assert not logger.path.with_suffix(".jsonl.3").exists()

    def test_no_rotation_when_under_size(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            logger = AuditLogger(path=path)
            monkeypatch.setattr(logger, "_MAX_FILE_SIZE_MB", 100)
            logger.write(
                event_type="test", actor="a", action="GET",
                resource="/", outcome="success",
            )
            backup = logger.path.with_suffix(".jsonl.1")
            assert not backup.exists()
