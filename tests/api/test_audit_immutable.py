"""Tests for T3 — Immutable Audit Logs with hash chain.

Covers:
- Hash chain linkage (prev_hash correctness)
- verify_chain detects tampering
- verify_chain passes on intact log
- API endpoint returns correct structure
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from uar.core.audit import AuditLogger


@pytest.fixture(autouse=True)
def setup_api_keys():
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


@pytest.fixture()
def client():
    from uar.api.server import app

    return TestClient(app, raise_server_exceptions=True)


def _make_logger() -> AuditLogger:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    return AuditLogger(path=path)


def test_hash_chain_links_correctly():
    """Each record's prev_hash matches the previous record's hash."""
    logger = _make_logger()

    logger.write(
        event_type="test",
        actor="alice",
        action="GET",
        resource="/runs",
        outcome="success",
    )
    logger.write(
        event_type="test",
        actor="bob",
        action="POST",
        resource="/runs",
        outcome="success",
    )

    recs = logger.list_records()
    assert len(recs) == 2
    assert recs[0]["prev_hash"] == ""
    assert recs[1]["prev_hash"] == recs[0]["hash"]


def test_verify_chain_passes_intact_log():
    """verify_chain returns ok=True on an untampered log."""
    logger = _make_logger()

    for i in range(3):
        logger.write(
            event_type="test",
            actor="user",
            action="GET",
            resource=f"/res{i}",
            outcome="success",
        )

    ok, failures = logger.verify_chain()
    assert ok is True
    assert failures == []


def test_verify_chain_detects_tampering():
    """verify_chain detects a tampered record."""
    logger = _make_logger()

    logger.write(
        event_type="test",
        actor="alice",
        action="GET",
        resource="/runs",
        outcome="success",
    )
    logger.write(
        event_type="test",
        actor="bob",
        action="POST",
        resource="/runs",
        outcome="success",
    )

    # Tamper with the file: change actor in first record
    lines = logger.path.read_text().strip().splitlines()
    rec0 = json.loads(lines[0])
    rec0["actor"] = "eve"
    lines[0] = json.dumps(rec0, sort_keys=True)
    logger.path.write_text("\n".join(lines) + "\n")

    ok, failures = logger.verify_chain()
    assert ok is False
    assert len(failures) >= 1
    # First record hash mismatch, second record prev_hash mismatch
    errors = {f["error"] for f in failures}
    assert "hash_mismatch" in errors or "prev_hash_mismatch" in errors


def test_api_audit_verify_endpoint(client):
    """GET /api/uar/admin/audit/verify returns chain status."""
    resp = client.get(
        "/api/uar/admin/audit/verify",
        headers={"Authorization": "Bearer dev-key-12345"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "record_count" in data
    assert "failures_count" in data
    assert isinstance(data["ok"], bool)
