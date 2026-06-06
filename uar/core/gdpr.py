"""GDPR data-subject request controller (T12).

Handles:
- Data portability (export all records for a user)
- Right to erasure (delete all records for a user)
- Privacy policy metadata
"""

from __future__ import annotations

from typing import Any, Dict

from uar.memory.base_store import RunStoreProtocol


class GDPRController:
    """Process data-subject requests against a RunStore."""

    def __init__(self, store: RunStoreProtocol) -> None:
        self.store = store

    def export_data(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Return all run records and metadata for *user_id*.

        Output is a plain dict suitable for JSON export (data portability).
        """
        records = self.store.list_records(user_id=user_id, limit=100_000)
        meta_keys = self.store.list_meta_keys()
        metadata = {k: self.store.get_metadata(k) for k in meta_keys}
        return {
            "user_id": user_id,
            "run_records": records,
            "metadata": metadata,
            "record_count": len(records),
        }

    def erase_data(self, user_id: str) -> int:
        """Delete every run record belonging to *user_id*.

        Returns the number of records removed.
        """
        records = self.store.list_records(user_id=user_id, limit=100_000)
        removed = 0
        for row in records:
            run_id = row.get("run_id") or row.get("id")
            if run_id and self.store.delete(run_id):
                removed += 1
        return removed

    def policy_metadata(self) -> Dict[str, Any]:
        """Return privacy-policy metadata for the API."""
        return {
            "data_controller": "UAR Operator",
            "retention_days": 30,
            "lawful_basis": "legitimate_interest",
            "rights": [
                "access",
                "erasure",
                "portability",
                "rectification",
            ],
            "contact": "privacy@uar.example.com",
        }
