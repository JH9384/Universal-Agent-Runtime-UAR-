"""Tests for T2 — Encryption at Rest (SQLite/Postgres/JSONL).

Covers:
- Pass-through when no key is configured
- Fernet encrypt/decrypt round-trip for all JSON columns
- Backwards-compatible plaintext reading
- Metadata key-value store encryption
"""

from __future__ import annotations

import os
import tempfile

from uar.core.contracts import RunRecord
from uar.memory.encryption import (
    EncryptedRunStore,
    _get_fernet,
    maybe_encrypt_store,
)
from uar.memory.sqlite_store import SqliteRunStore


def _make_key() -> str:
    """Generate a fresh Fernet key for testing."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def _make_store() -> SqliteRunStore:
    """Create an isolated SqliteRunStore backed by a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return SqliteRunStore(path=path)


def test_no_key_returns_plain_store():
    """When UAR_ENCRYPTION_KEY is not set, maybe_encrypt_store is a pass-through."""
    os.environ.pop("UAR_ENCRYPTION_KEY", None)
    inner = _make_store()
    store = maybe_encrypt_store(inner)
    assert store is inner


def test_encrypt_decrypt_round_trip():
    """EncryptedRunStore transparently encrypts and decrypts JSON fields."""
    key = _make_key()
    inner = _make_store()
    store = EncryptedRunStore(inner, key=key)

    record = RunRecord(
        run_id="r1",
        goal_id="g1",
        skills=["echo", "noop"],
        status="completed",
        events=[{"type": "start"}, {"type": "end"}],
        outputs={"result": "ok"},
        metadata={"user": "alice"},
        uor_address="uor://test",
        uor_witness={"signature": "abc"},
    )
    store.append(record)

    # Read back — must be identical to original
    row = store.get_by_run_id("r1")
    assert row is not None
    assert row["skills"] == ["echo", "noop"]
    assert row["events"] == [{"type": "start"}, {"type": "end"}]
    assert row["outputs"] == {"result": "ok"}
    assert row["metadata"] == {"user": "alice"}
    assert row["uor_witness"] == {"signature": "abc"}


def test_inner_store_has_encrypted_values():
    """The underlying store receives encrypted JSON blobs."""
    key = _make_key()
    inner = _make_store()
    store = EncryptedRunStore(inner, key=key)

    record = RunRecord(
        run_id="r2",
        goal_id="g1",
        skills=["a"],
        status="completed",
        events=[],
        outputs={},
        metadata={},
    )
    store.append(record)

    # Read directly from inner store — values should be ciphertext
    raw = inner.get_by_run_id("r2")
    assert raw is not None
    # skills should NOT be a plain list
    assert not isinstance(raw["skills"], list)
    # It should be a Fernet token (starts with 'gAAAA')
    assert str(raw["skills"]).startswith("gAAAA")


def test_backwards_compatible_plaintext_read():
    """EncryptedRunStore can read rows stored before encryption."""
    key = _make_key()
    inner = _make_store()

    # Write plaintext record directly to inner store
    inner.append(
        RunRecord(
            run_id="r3",
            goal_id="g1",
            skills=["plain"],
            status="completed",
            events=[],
            outputs={},
            metadata={},
        )
    )

    # Now wrap with encryption and read back
    store = EncryptedRunStore(inner, key=key)
    row = store.get_by_run_id("r3")
    assert row is not None
    assert row["skills"] == ["plain"]


def test_metadata_encryption():
    """put_metadata / get_metadata encrypts and decrypts values."""
    key = _make_key()
    inner = _make_store()
    store = EncryptedRunStore(inner, key=key)

    store.put_metadata("fleet_state", {"nodes": ["n1", "n2"]})
    value = store.get_metadata("fleet_state")
    assert value == {"nodes": ["n1", "n2"]}


def test_metadata_backwards_compatible_plaintext():
    """get_metadata returns plaintext values that were stored before encryption."""
    key = _make_key()
    inner = _make_store()
    inner.put_metadata("legacy", {"old": True})

    store = EncryptedRunStore(inner, key=key)
    value = store.get_metadata("legacy")
    assert value == {"old": True}


def test_invalid_key_logs_error():
    """An invalid Fernet key results in None fernet (encryption disabled)."""
    fernet = _get_fernet("not-a-valid-key")
    assert fernet is None


def test_list_records_decrypts():
    """list_records decrypts all rows."""
    key = _make_key()
    inner = _make_store()
    store = EncryptedRunStore(inner, key=key)

    for i in range(3):
        store.append(
            RunRecord(
                run_id=f"lr{i}",
                goal_id="g1",
                skills=[f"skill{i}"],
                status="completed",
                events=[],
                outputs={},
                metadata={},
            )
        )

    inner.flush()
    rows = store.list_records(limit=100)
    skills = {r["skills"][0] for r in rows}
    assert skills == {"skill0", "skill1", "skill2"}
