"""Generic metadata-backed entity store for operator entities.

Reusable persistence layer used by incidents, snapshots, inbox,
investigations, and any future metadata entity.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

from uar.api.state import store

logger = logging.getLogger(__name__)


class MetadataEntityStore:
    """Load/persist small JSON entities via the store's metadata API.

    Each entity lives at ``{namespace}:{entity_id}`` and is stored as
    JSON.  The store is expected to expose ``get_metadata``, and
    optionally ``put_metadata`` or ``put_meta``.  Corrupt records are
    skipped with a warning rather than crashing the caller.
    """

    def __init__(
        self,
        namespace: str,
        *,
        id_field: str = "id",
        sort_field: str = "created_at",
        max_index_scan: int = 100,
        use_list_meta_keys: bool = True,
    ) -> None:
        self._namespace = namespace
        self._id_field = id_field
        self._sort_field = sort_field
        self._max_index_scan = max_index_scan
        self._use_list_meta_keys = use_list_meta_keys

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def key(self, entity_id: str) -> str:
        return f"{self._namespace}:{entity_id}"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, entity: Dict[str, Any]) -> None:
        """Save *entity* to the metadata store.  Swallows errors."""
        entity_id = entity.get(self._id_field)
        if entity_id is None:
            logger.warning(
                "Cannot persist entity without '%s' field", self._id_field
            )
            return
        key = self.key(entity_id)
        try:
            if hasattr(store, "put_metadata"):
                store.put_metadata(key, entity)
            elif hasattr(store, "put_meta"):
                store.put_meta(key, json.dumps(entity))
        except Exception as exc:
            logger.warning("%s persistence failed: %s", self._namespace, exc)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Return a single entity by its ``id_field`` value, or None."""
        try:
            raw = store.get_metadata(self.key(entity_id))
            if raw:
                return self._decode(raw)
        except Exception as exc:
            logger.warning("%s load_by_id failed: %s", self._namespace, exc)
        return None

    def load_all(self) -> List[Dict[str, Any]]:
        """Return all known entities, sorted newest-first by *sort_field*."""
        entities: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        # 1. Scan via list_meta_keys if available
        if self._use_list_meta_keys and hasattr(store, "list_meta_keys"):
            try:
                for k in store.list_meta_keys():
                    if not k.startswith(f"{self._namespace}:"):
                        continue
                    raw = store.get_metadata(k)
                    entity = self._decode(raw)
                    if entity is None:
                        continue
                    eid = entity.get(self._id_field)
                    if eid and eid not in seen:
                        seen.add(eid)
                        entities.append(entity)
            except Exception as exc:
                logger.warning(
                    "%s list_meta_keys scan failed: %s", self._namespace, exc
                )

        # 2. Fallback: sequential index scan
        try:
            for i in range(self._max_index_scan):
                suffix = self._namespace.split(":")[-1]
                test_key = f"{self._namespace}:{suffix}-{i}"
                raw = store.get_metadata(test_key)
                entity = self._decode(raw)
                if entity is None:
                    continue
                eid = entity.get(self._id_field)
                if eid and eid not in seen:
                    seen.add(eid)
                    entities.append(entity)
        except Exception as exc:
            logger.warning("%s index scan failed: %s", self._namespace, exc)

        return sorted(
            entities,
            key=lambda x: x.get(self._sort_field, 0),
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def delete_by_id(self, entity_id: str) -> bool:
        """Delete a single entity if the metadata backend supports deletion."""
        key = self.key(entity_id)
        try:
            if hasattr(store, "delete_metadata"):
                store.delete_metadata(key)
                return True
            if hasattr(store, "delete_meta"):
                store.delete_meta(key)
                return True
        except Exception as exc:
            logger.warning(
                "%s delete failed for %s: %s", self._namespace, key, exc
            )
        return False

    def prune_to_limit(self, limit: int) -> int:
        """Keep only the newest *limit* entities for this namespace.

        Requires ``list_meta_keys`` for complete discovery. If the store cannot
        enumerate metadata keys, this is a no-op rather than risking partial
        deletion through the sequential fallback path.
        """
        if limit <= 0:
            return 0
        if not hasattr(store, "list_meta_keys"):
            return 0

        entities: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        try:
            for key in store.list_meta_keys():
                if not key.startswith(f"{self._namespace}:"):
                    continue
                raw = store.get_metadata(key)
                entity = self._decode(raw)
                if entity is None:
                    continue
                eid = entity.get(self._id_field)
                if eid is None:
                    continue
                eid_s = str(eid)
                if eid_s in seen:
                    continue
                seen.add(eid_s)
                entities.append(entity)
        except Exception as exc:
            logger.warning(
                "%s retention scan failed: %s", self._namespace, exc
            )
            return 0

        entities.sort(
            key=lambda x: x.get(self._sort_field, 0),
            reverse=True,
        )
        removed = 0
        for entity in entities[limit:]:
            eid = entity.get(self._id_field)
            if eid is not None and self.delete_by_id(str(eid)):
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _decode(self, raw: Any) -> Optional[Dict[str, Any]]:
        """Parse metadata value; return None on corruption."""
        try:
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, dict):
                return raw
        except Exception as exc:
            logger.debug("Corrupt %s JSON: %s", self._namespace, exc)
        return None
