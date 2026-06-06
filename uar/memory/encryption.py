"""Encryption-at-rest layer for UAR run stores.

T2 — Encryption at Rest (SQLite/Postgres/JSONL).

Wraps any RunStoreProtocol and transparently encrypts/decrypts JSON
values in run records.  When no key is configured the wrapper is a
pass-through (no encryption, no overhead).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord
from uar.memory.base_store import RunStoreProtocol

logger = logging.getLogger(__name__)

# Columns that carry JSON blobs and should be encrypted
_ENCRYPTED_JSON_COLUMNS = frozenset(
    {"skills", "events", "outputs", "metadata", "uor_witness"}
)


def _get_fernet(key: Optional[str] = None):
    """Return a Fernet instance or None if no key is available."""
    raw = key or os.getenv("UAR_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        from cryptography.fernet import Fernet
    except Exception:  # pragma: no cover - optional dep
        logger.warning("cryptography not installed; encryption disabled")
        return None

    # Accept base64-encoded 32-byte key
    try:
        return Fernet(raw.encode())
    except Exception:
        # If key is not a valid Fernet key, log and return None
        logger.error(
            "UAR_ENCRYPTION_KEY is not a valid Fernet key; "
            "generate one with Fernet.generate_key()"
        )
        return None


class EncryptedRunStore:
    """Transparent encryption wrapper around any RunStoreProtocol.

    Encrypts JSON blob columns (skills, events, outputs, metadata,
    uor_witness) before passing them to the underlying store, and
    decrypts them on read-back.  All other columns pass through
    unchanged.

    When ``UAR_ENCRYPTION_KEY`` is not set the wrapper is a no-op
    passthrough.
    """

    def __init__(
        self,
        store: RunStoreProtocol,
        key: Optional[str] = None,
    ) -> None:
        self._store = store
        self._fernet = _get_fernet(key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        if self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        if self._fernet is None:
            return ciphertext
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def _encrypt_record(self, record: RunRecord) -> RunRecord:
        """Return a copy with encrypted JSON fields."""
        if self._fernet is None:
            return record

        # Build a new dict from the record
        data: Dict[str, Any] = {}
        for field in RunRecord.__dataclass_fields__:
            val = getattr(record, field)
            if field in _ENCRYPTED_JSON_COLUMNS and val is not None:
                data[field] = self._encrypt(json.dumps(val))
            else:
                data[field] = val
        return RunRecord(**data)

    def _decrypt_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy with decrypted JSON fields."""
        if self._fernet is None:
            return row

        result = dict(row)
        for col in _ENCRYPTED_JSON_COLUMNS:
            if col in result and result[col] is not None:
                try:
                    decrypted = self._decrypt(str(result[col]))
                    result[col] = json.loads(decrypted)
                except Exception:
                    # If decryption fails, assume plaintext (backwards
                    # compatible migration path)
                    pass
        return result

    # ------------------------------------------------------------------
    # RunStoreProtocol delegation
    # ------------------------------------------------------------------

    def append(self, record: RunRecord) -> None:
        self._store.append(self._encrypt_record(record))

    def append_many(self, records: List[RunRecord]) -> None:
        # type: ignore[override] — not in protocol but present on stores
        for r in records:
            self.append(r)

    def list_records(
        self,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        rows = self._store.list_records(user_id, limit)
        return [self._decrypt_dict(r) for r in rows]

    def list_all(
        self,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        # type: ignore[override]
        rows = self._store.list_all(user_id, limit)
        return [self._decrypt_dict(r) for r in rows]

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._store.get_by_run_id(run_id)
        if row is None:
            return None
        return self._decrypt_dict(row)

    def flush(self) -> None:
        self._store.flush()

    def delete(self, run_id: str) -> bool:
        return self._store.delete(run_id)

    def purge_old_records(self, retention_days: int) -> int:
        return self._store.purge_old_records(retention_days)

    # Feedback / shown / outcome / metadata passthrough
    def record_feedback(
        self,
        recommendation_id: str,
        action: str,
        user_id: Optional[str] = None,
    ) -> None:
        self._store.record_feedback(
            recommendation_id, action, user_id
        )

    def get_feedback(
        self,
        recommendation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return self._store.get_feedback(
            recommendation_id, user_id, limit
        )

    def record_recommendation_shown(
        self,
        recommendation_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        self._store.record_recommendation_shown(
            recommendation_id, user_id
        )

    def get_shown_recommendations(
        self,
        recommendation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return self._store.get_shown_recommendations(
            recommendation_id, user_id, limit
        )

    def record_outcome(
        self,
        recommendation_id: str,
        outcome_type: str,
    ) -> None:
        self._store.record_outcome(
            recommendation_id, outcome_type
        )

    def get_outcomes(
        self,
        recommendation_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return self._store.get_outcomes(
            recommendation_id, limit
        )

    def record_recommendation_metadata(
        self,
        recommendation_id: str,
        category: str,
        source: str = "",
        title: str = "",
        confidence: float = 0.0,
        run_id: str = "",
    ) -> None:
        self._store.record_recommendation_metadata(
            recommendation_id,
            category,
            source,
            title,
            confidence,
            run_id,
        )

    def get_recommendation_metadata(
        self,
        recommendation_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return self._store.get_recommendation_metadata(
            recommendation_id, limit
        )

    # Metadata key-value store with transparent encryption
    def put_metadata(self, key: str, value: Any) -> None:
        if self._fernet is not None:
            value = self._encrypt(json.dumps(value))
        self._store.put_metadata(key, value)

    def get_metadata(self, key: str) -> Optional[Any]:
        value = self._store.get_metadata(key)
        if value is None or self._fernet is None:
            return value
        try:
            decrypted = self._decrypt(str(value))
            return json.loads(decrypted)
        except Exception:
            # Backwards-compatible: plaintext metadata
            return value

    def list_meta_keys(self) -> List[str]:
        return self._store.list_meta_keys()


def maybe_encrypt_store(
    store: RunStoreProtocol,
    key: Optional[str] = None,
) -> RunStoreProtocol:
    """Wrap *store* in EncryptedRunStore if a key is available.

    Returns *store* unchanged when no key is configured.
    """
    raw = key or os.getenv("UAR_ENCRYPTION_KEY", "").strip()
    if not raw:
        return store
    return EncryptedRunStore(store, key=raw)
