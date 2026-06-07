"""Integrity checkers for metadata-backed operator entities.

Light-weight diagnostics that can be called from health endpoints
or periodic maintenance tasks to detect store drift, orphaned keys,
and corrupted records.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from uar.api.state import store
from uar.api.routers.operator.helpers.entity_store import MetadataEntityStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntegrityReport:
    """Summary of a single entity namespace scan."""

    namespace: str
    total_keys: int
    valid_records: int
    corrupt_records: int
    orphan_ids: List[str]

    @property
    def is_healthy(self) -> bool:
        return self.corrupt_records == 0 and not self.orphan_ids


def check_entity_integrity(
    store_instance: MetadataEntityStore,
    *,
    expected_fields: Optional[List[str]] = None,
) -> IntegrityReport:
    """Scan every key under *store_instance*'s namespace and report issues.

    * **Corrupt** — JSON that fails to parse.
    * **Orphan**  — key exists but record has no ``id_field`` value, so
      it is unreachable by normal load_all/load_by_id logic.
    """
    namespace = store_instance._namespace
    expected = expected_fields or [store_instance._id_field]

    total_keys = 0
    valid_records = 0
    corrupt_records = 0
    orphan_ids: List[str] = []

    def _inspect_key(key: str) -> None:
        nonlocal total_keys, valid_records, corrupt_records
        total_keys += 1
        try:
            raw = store.get_metadata(key)
        except Exception as exc:
            logger.debug("Failed to read %s: %s", key, exc)
            corrupt_records += 1
            return

        if raw is None:
            return

        # Decode
        try:
            if isinstance(raw, str):
                record: Dict[str, Any] = json.loads(raw)
            elif isinstance(raw, dict):
                record = raw
            else:
                corrupt_records += 1
                return
        except Exception:
            corrupt_records += 1
            return

        # Validate expected fields
        missing = [f for f in expected if f not in record]
        if missing:
            orphan_ids.append(key)
            return

        # Validate ID presence
        entity_id = record.get(store_instance._id_field)
        if entity_id is None:
            orphan_ids.append(key)
            return

        valid_records += 1

    # Scan via list_meta_keys if available
    if hasattr(store, "list_meta_keys"):
        try:
            for key in store.list_meta_keys():
                if key.startswith(f"{namespace}:"):
                    _inspect_key(key)
        except Exception as exc:
            logger.warning(
                "Integrity check list_meta_keys failed: %s", exc
            )

    return IntegrityReport(
        namespace=namespace,
        total_keys=total_keys,
        valid_records=valid_records,
        corrupt_records=corrupt_records,
        orphan_ids=orphan_ids,
    )
