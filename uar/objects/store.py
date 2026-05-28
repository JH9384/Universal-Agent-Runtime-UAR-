"""Thread-safe SQLite-backed store for UOR objects, lineage, and runtimes.

The store keeps an authoritative on-disk SQLite database **and** in-memory
mirrors for fast read paths. All writes go through the database first; the
in-memory mirror is updated under an :class:`threading.RLock` to prevent
read-modify-write races under FastAPI's threadpool.

The default DB path is configurable via ``UOR_DB_PATH`` (or the legacy
``DB_PATH`` env var). Tests typically construct an :class:`ObjectStore`
with an explicit ``db_path`` pointing to a tmp directory.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_FILENAME = "uar.sqlite3"


def _resolve_default_db_path() -> str:
    """Return DB path from settings, with env-var fallback.

    Resolution order:
      1. ``uar.config.config.uor_db_path`` (centralized settings)
      2. ``UOR_DB_PATH`` env var (preferred legacy)
      3. ``DB_PATH`` env var (oldest legacy)
      4. ``DEFAULT_DB_FILENAME`` (CWD-relative)
    """
    try:
        from uar.config import config

        path = getattr(config, "uor_db_path", None)
        if path is not None:
            return str(path)
    except Exception:  # pragma: no cover - circular-import safety net
        pass
    return (
        os.getenv("UOR_DB_PATH") or os.getenv("DB_PATH") or DEFAULT_DB_FILENAME
    )


class ObjectStore:
    """SQLite + in-memory mirror for UOR objects, lineage, and runtimes.

    Construct one per FastAPI app (the default app uses
    :func:`get_default_store`). Tests may construct their own and inject
    via dependency overrides.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path: str = db_path or _resolve_default_db_path()
        self._lock = threading.RLock()
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._lineage: Dict[str, List[Dict[str, Any]]] = {}
        self._runtime_registry: Dict[str, str] = {}
        self.init_db()
        self.load_db()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL gives us better read concurrency; safe for our workload.
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:  # pragma: no cover - exotic FS
            pass
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS objects ("
                "digest TEXT PRIMARY KEY, "
                "record_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS lineage ("
                "digest TEXT NOT NULL, "
                "event_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS runtime_registry ("
                "name TEXT PRIMARY KEY, "
                "digest TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS object_content ("
                "digest TEXT PRIMARY KEY, "
                "media_type TEXT NOT NULL, "
                "content_bytes BLOB NOT NULL, "
                "created_at TEXT NOT NULL"
                ")"
            )
            conn.commit()

    def load_db(self) -> None:
        """Refresh in-memory mirrors from the SQLite store."""
        with self._lock, self._connect() as conn:
            self._objects.clear()
            self._lineage.clear()
            self._runtime_registry.clear()
            for row in conn.execute("SELECT digest, record_json FROM objects"):
                try:
                    self._objects[row["digest"]] = json.loads(
                        row["record_json"]
                    )
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping corrupted object row: %s", row["digest"]
                    )
            for row in conn.execute("SELECT digest, event_json FROM lineage"):
                try:
                    self._lineage.setdefault(row["digest"], []).append(
                        json.loads(row["event_json"])
                    )
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping corrupted lineage row: %s", row["digest"]
                    )
            for row in conn.execute(
                "SELECT name, digest FROM runtime_registry"
            ):
                self._runtime_registry[row["name"]] = row["digest"]

    # ------------------------------------------------------------------
    # Object operations
    # ------------------------------------------------------------------
    def has_object(self, digest: str) -> bool:
        with self._lock:
            return digest in self._objects

    def get_object(self, digest: str) -> Dict[str, Any]:
        with self._lock:
            obj = self._objects.get(digest)
        if obj is None:
            raise KeyError(digest)
        return obj

    def store_content(
        self, digest: str, media_type: str, content: bytes
    ) -> None:
        """Store binary content keyed by object digest."""
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO object_content "
                "(digest, media_type, content_bytes, created_at) "
                "VALUES (?, ?, ?, ?)",
                (digest, media_type, content, created_at),
            )
            conn.commit()

    def get_content(self, digest: str) -> Optional[Dict[str, Any]]:
        """Retrieve binary content for a digest.

        Returns a dict with ``media_type``, ``content_bytes``, and
        ``created_at`` keys, or ``None`` if no content exists.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT media_type, content_bytes, created_at "
                "FROM object_content WHERE digest = ?",
                (digest,),
            ).fetchone()
        if row is None:
            return None
        return {
            "media_type": row["media_type"],
            "content_bytes": row["content_bytes"],
            "created_at": row["created_at"],
        }

    def put_object(self, record: Dict[str, Any]) -> None:
        digest = record["digest"]
        payload = json.dumps(record, sort_keys=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO objects (digest, record_json) "
                "VALUES (?, ?)",
                (digest, payload),
            )
            conn.commit()
            self._objects[digest] = record

    def iter_objects(self) -> Iterator[tuple[str, Dict[str, Any]]]:
        with self._lock:
            # Snapshot to avoid holding the lock during iteration.
            snapshot = list(self._objects.items())
        return iter(snapshot)

    # ------------------------------------------------------------------
    # Lineage operations
    # ------------------------------------------------------------------
    def append_lineage(self, digest: str, event: Dict[str, Any]) -> None:
        payload = json.dumps(event, sort_keys=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO lineage (digest, event_json) VALUES (?, ?)",
                (digest, payload),
            )
            conn.commit()
            self._lineage.setdefault(digest, []).append(event)

    def get_lineage(self, digest: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._lineage.get(digest, []))

    # ------------------------------------------------------------------
    # Runtime registry operations
    # ------------------------------------------------------------------
    def register_runtime(self, name: str, digest: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO runtime_registry "
                "(name, digest) VALUES (?, ?)",
                (name, digest),
            )
            conn.commit()
            self._runtime_registry[name] = digest

    def get_runtime_digest(self, name: str) -> Optional[str]:
        with self._lock:
            return self._runtime_registry.get(name)

    def list_runtimes(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._runtime_registry)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------
    def reset_in_memory(self) -> None:
        """Clear in-memory mirrors only (used by some test fixtures)."""
        with self._lock:
            self._objects.clear()
            self._lineage.clear()
            self._runtime_registry.clear()


# ----------------------------------------------------------------------
# Default store (used by FastAPI routers when not overridden in tests)
# ----------------------------------------------------------------------
_default_store: Optional[ObjectStore] = None
_default_store_lock = threading.Lock()


def get_default_store() -> ObjectStore:
    """Return the process-wide default :class:`ObjectStore` (lazy init)."""
    global _default_store
    if _default_store is None:
        with _default_store_lock:
            if _default_store is None:
                _default_store = ObjectStore()
    return _default_store


def set_default_store(store: Optional[ObjectStore]) -> None:
    """Replace (or clear) the default store. Intended for tests."""
    global _default_store
    with _default_store_lock:
        _default_store = store


__all__ = [
    "DEFAULT_DB_FILENAME",
    "ObjectStore",
    "get_default_store",
    "set_default_store",
]
