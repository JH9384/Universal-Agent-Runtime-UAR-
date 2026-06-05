"""Data source registry for tracking UAR-connected data sources.

Manages run stores, external APIs, and file-based sources with health
status and metadata. Persisted in store metadata for cross-session
survival.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class DataSource:
    """A registered data source."""

    id: str
    source_type: str  # 'postgres' | 'sqlite' | 'json' | 'autonomi' | 'api'
    location: str  # connection string, path, or URL
    description: str = ""
    healthy: bool = True
    last_check_at: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class _StoreAdapter(Protocol):
    """Minimal interface needed from a store."""

    def put_metadata(self, key: str, value: Any) -> None: ...

    def get_metadata(self, key: str) -> Any: ...

    def list_meta_keys(self) -> List[str]: ...


class DataSourceRegistry:
    """Registry of data sources backed by store metadata."""

    _META_PREFIX = "uar:datasource:"

    def __init__(self, store: _StoreAdapter):
        self._store = store

    def _key(self, dsid: str) -> str:
        return f"{self._META_PREFIX}{dsid}"

    def list_sources(self) -> List[DataSource]:
        """Return all registered data sources."""
        sources: List[DataSource] = []
        try:
            keys = self._store.list_meta_keys()
        except Exception:
            keys = [f"{self._META_PREFIX}{i}" for i in range(50)]
        for key in keys:
            if not key.startswith(self._META_PREFIX):
                continue
            try:
                raw = self._store.get_metadata(key)
                if not raw:
                    continue
                import json

                data = json.loads(raw) if isinstance(raw, str) else raw
                sources.append(DataSource(**data))
            except Exception as exc:
                logger.debug("Skipping corrupt source %s: %s", key, exc)
        return sorted(sources, key=lambda s: s.id)

    def get_source(self, dsid: str) -> Optional[DataSource]:
        """Fetch a single data source by ID."""
        try:
            raw = self._store.get_metadata(self._key(dsid))
            if not raw:
                return None
            import json

            data = json.loads(raw) if isinstance(raw, str) else raw
            return DataSource(**data)
        except Exception as exc:
            logger.warning("Failed to get source %s: %s", dsid, exc)
            return None

    def register(
        self,
        dsid: str,
        source_type: str,
        location: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataSource:
        """Register or update a data source."""
        existing = self.get_source(dsid)
        now = time.time()
        source = DataSource(
            id=dsid,
            source_type=source_type,
            location=location,
            description=description,
            healthy=existing.healthy if existing else True,
            last_check_at=existing.last_check_at if existing else None,
            error=existing.error if existing else None,
            metadata=metadata or existing.metadata if existing else {},
            created_at=existing.created_at if existing else now,
        )
        import json

        self._store.put_metadata(self._key(dsid), json.dumps(asdict(source)))
        logger.info("Registered data source %s (%s)", dsid, source_type)
        return source

    def deregister(self, dsid: str) -> bool:
        """Remove a data source. Returns True if existed."""
        try:
            raw = self._store.get_metadata(self._key(dsid))
            if raw:
                self._store.put_metadata(self._key(dsid), "")
                logger.info("Deregistered data source %s", dsid)
                return True
        except Exception as exc:
            logger.warning("Failed to deregister source %s: %s", dsid, exc)
        return False

    def check_health(self, dsid: str) -> DataSource:
        """Run a health check on a data source and update its status."""
        source = self.get_source(dsid)
        if source is None:
            raise ValueError(f"Source '{dsid}' not found")

        ok = False
        msg = ""
        try:
            if source.source_type == "postgres":
                ok, msg = self._check_postgres(source.location)
            elif source.source_type == "sqlite":
                ok, msg = self._check_sqlite(source.location)
            elif source.source_type == "json":
                ok, msg = self._check_json(source.location)
            elif source.source_type == "api":
                ok, msg = self._check_api(source.location)
            else:
                ok, msg = True, "No health check implemented"
        except Exception as exc:
            ok = False
            msg = str(exc)

        source.healthy = ok
        source.error = None if ok else msg
        source.last_check_at = time.time()
        import json

        self._store.put_metadata(self._key(dsid), json.dumps(asdict(source)))
        return source

    def _check_postgres(self, url: str) -> tuple[bool, str]:
        try:
            import psycopg2

            conn = psycopg2.connect(url, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True, "Connected"
        except Exception as exc:
            return False, str(exc)

    def _check_sqlite(self, path: str) -> tuple[bool, str]:
        from pathlib import Path

        p = Path(path)
        if p.exists():
            return True, "File exists"
        return False, "File not found"

    def _check_json(self, path: str) -> tuple[bool, str]:
        from pathlib import Path

        p = Path(path)
        if p.exists():
            return True, "Directory exists"
        return False, "Directory not found"

    def _check_api(self, url: str) -> tuple[bool, str]:
        import urllib.request

        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status < 500, f"HTTP {resp.status}"
        except Exception as exc:
            return False, str(exc)

    def auto_register_stores(self) -> List[DataSource]:
        """Auto-register currently configured UAR store backends."""
        sources: List[DataSource] = []

        db_url = os.getenv("UAR_DATABASE_URL", "").strip()
        if db_url:
            # Mask credentials in the location string
            safe = db_url.split("@")[-1] if "@" in db_url else db_url
            sources.append(
                self.register(
                    "default_postgres",
                    "postgres",
                    f"postgres://{safe}",
                    "Auto-registered PostgreSQL run store",
                )
            )

        sqlite_path = os.getenv("UAR_SQLITE_PATH", "").strip()
        if sqlite_path:
            sources.append(
                self.register(
                    "default_sqlite",
                    "sqlite",
                    sqlite_path,
                    "Auto-registered SQLite run store",
                )
            )

        if not db_url and not sqlite_path:
            sources.append(
                self.register(
                    "default_json",
                    "json",
                    str(os.getenv("PROJECT_ROOT", ".")),
                    "Auto-registered JSONL run store",
                )
            )

        return sources


# Global singleton
_registry: Optional[DataSourceRegistry] = None


def get_data_source_registry(
    store: Optional[_StoreAdapter] = None,
) -> DataSourceRegistry:
    """Return the global DataSourceRegistry, lazily initialised."""
    global _registry
    if _registry is None:
        if store is None:
            from uar.api.state import store as _store

            store = _store
        _registry = DataSourceRegistry(store)
    return _registry
