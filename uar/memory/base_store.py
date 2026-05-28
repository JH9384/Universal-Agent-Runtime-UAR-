"""Base protocol and shared helpers for UAR run stores.

All concrete stores (JsonRunStore, SqliteRunStore, PostgresRunStore)
satisfy :class:`RunStoreProtocol`.  Code that needs to be store-agnostic
should type-hint against the protocol rather than a concrete class.

:func:`run_record_from_dict` is the single authoritative place that
converts a raw store row (dict) into a :class:`~uar.core.contracts.RunRecord`.
It filters out store-internal columns (e.g. ``id``, ``created_at``)
that are not fields of ``RunRecord``, preventing ``TypeError`` crashes
when different backends return different column sets.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from uar.core.contracts import RunRecord

_RUNRECORD_FIELDS = frozenset(
    RunRecord.__dataclass_fields__.keys()  # type: ignore[attr-defined]
)


def run_record_from_dict(row: Dict[str, Any]) -> RunRecord:
    """Convert a raw store row dict into a :class:`RunRecord`.

    Extra keys present in the dict (e.g. ``created_at``, ``id``)
    that are not ``RunRecord`` fields are silently dropped so this
    works with every store backend.

    Args:
        row: A dict as returned by any store's ``list_records()``
             or ``get_by_run_id()`` method.

    Returns:
        A fully-constructed :class:`RunRecord`.

    Raises:
        TypeError: If a required ``RunRecord`` field (``run_id``,
                   ``goal_id``, ``skills``) is missing from *row*.
    """
    filtered = {k: v for k, v in row.items() if k in _RUNRECORD_FIELDS}
    return RunRecord(**filtered)


@runtime_checkable
class RunStoreProtocol(Protocol):
    """Structural protocol satisfied by all UAR run store implementations.

    Type-hint parameters and return values against this instead of
    a concrete store class so code works with Json, Sqlite, and Postgres
    backends transparently.
    """

    def append(self, record: RunRecord) -> None: ...

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]: ...

    def list_all(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]: ...

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]: ...

    def flush(self) -> None: ...

    def purge_old_records(self, retention_days: int) -> int: ...


def get_store() -> RunStoreProtocol:
    """Return a concrete store matching the current environment.

    Selection order:
      1. ``UAR_DATABASE_URL`` set → ``PostgresRunStore``
      2. ``UAR_SQLITE_PATH`` set  → ``SqliteRunStore``
      3. Otherwise                → ``JsonRunStore``

    All three satisfy :class:`RunStoreProtocol` so callers work
    transparently across backends.
    """
    db_url = os.getenv("UAR_DATABASE_URL", "").strip()
    if db_url:
        from uar.memory.postgres_store import PostgresRunStore

        return PostgresRunStore(db_url)

    sqlite_path = os.getenv("UAR_SQLITE_PATH", "").strip()
    if sqlite_path:
        from uar.memory.sqlite_store import SqliteRunStore

        return SqliteRunStore(path=sqlite_path)

    from uar.memory.json_store import JsonRunStore

    return JsonRunStore()
