"""Regression coverage for operator snapshot discovery and retention."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


def test_snapshot_store_uses_list_meta_keys():
    """Timestamp-keyed snapshots require metadata key discovery."""
    from uar.api.routers.operator import common

    assert common._snapshot_store._use_list_meta_keys is True


def test_snapshot_load_all_discovers_timestamp_keys(monkeypatch):
    """Snapshots are keyed by timestamp, not snapshot-0 fallback ids."""
    from uar.api.routers.operator import common

    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = [
        "operator:snapshot:100",
        "operator:snapshot:300",
        "operator:snapshot:200",
        "operator:incident:ignore",
    ]
    fake_store.get_metadata.side_effect = lambda key: json.dumps(
        {"timestamp": int(key.rsplit(":", 1)[-1]), "trust_score": 0.5}
    )

    monkeypatch.setattr(common, "store", fake_store)
    monkeypatch.setattr(
        "uar.api.routers.operator.helpers.entity_store.store",
        fake_store,
    )

    snapshots = common._load_all_snapshots(limit=2)

    assert [s["timestamp"] for s in snapshots] == [300, 200]


def test_snapshot_persist_prunes_to_retention_limit(monkeypatch):
    """Persisting snapshots should trigger bounded retention cleanup."""
    from uar.api.routers.operator import common

    calls = []

    def fake_persist(snapshot):
        calls.append(("persist", snapshot["timestamp"]))

    def fake_prune(limit):
        calls.append(("prune", limit))
        return 0

    monkeypatch.setattr(common._snapshot_store, "persist", fake_persist)
    monkeypatch.setattr(common._snapshot_store, "prune_to_limit", fake_prune)

    common._persist_snapshot({"timestamp": 123})

    assert calls == [("persist", 123), ("prune", 168)]


def test_metadata_entity_store_prune_to_limit(monkeypatch):
    """Pruning keeps newest entities and deletes older timestamp records."""
    from uar.api.routers.operator.helpers.entity_store import (
        MetadataEntityStore,
    )
    import uar.api.routers.operator.helpers.entity_store as entity_store

    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = [
        "operator:snapshot:1",
        "operator:snapshot:2",
        "operator:snapshot:3",
    ]
    payloads = {
        "operator:snapshot:1": {"timestamp": 1},
        "operator:snapshot:2": {"timestamp": 2},
        "operator:snapshot:3": {"timestamp": 3},
    }
    fake_store.get_metadata.side_effect = lambda key: payloads[key]
    fake_store.delete_metadata = MagicMock()

    monkeypatch.setattr(entity_store, "store", fake_store)

    s = MetadataEntityStore(
        "operator:snapshot",
        id_field="timestamp",
        sort_field="timestamp",
        use_list_meta_keys=True,
    )
    removed = s.prune_to_limit(2)

    assert removed == 1
    fake_store.delete_metadata.assert_called_once_with("operator:snapshot:1")


def test_sqlite_delete_metadata_removes_key(tmp_path):
    from uar.memory.sqlite_store import SqliteRunStore

    db_file = str(tmp_path / "meta_delete.db")
    store = SqliteRunStore(db_file)
    try:
        store.put_metadata("operator:snapshot:1", {"timestamp": 1})
        assert store.get_metadata("operator:snapshot:1") == {"timestamp": 1}

        store.delete_metadata("operator:snapshot:1")

        assert store.get_metadata("operator:snapshot:1") is None
        assert "operator:snapshot:1" not in store.list_meta_keys()
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_json_delete_metadata_removes_key(tmp_path):
    from uar.memory.json_store import JsonRunStore

    store = JsonRunStore(path=tmp_path / "runs.jsonl")
    store.put_metadata("operator:snapshot:1", {"timestamp": 1})
    assert store.get_metadata("operator:snapshot:1") == {"timestamp": 1}

    store.delete_metadata("operator:snapshot:1")

    assert store.get_metadata("operator:snapshot:1") is None
    assert "operator:snapshot:1" not in store.list_meta_keys()
