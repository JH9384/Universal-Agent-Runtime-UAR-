"""Tests for missed branches in uar.objects.store."""

from unittest.mock import patch

from uar.objects.store import (
    ObjectStore,
    _resolve_default_db_path,
    get_default_store,
    set_default_store,
)


class TestResolveDefaultDbPath:
    def test_from_config(self):
        class FakeConfig:
            uor_db_path = "/tmp/from_config.db"

        with patch("uar.config.config", FakeConfig()):
            assert _resolve_default_db_path() == "/tmp/from_config.db"

    def test_from_env(self):
        with patch.dict("os.environ", {"UOR_DB_PATH": "/tmp/env.db"}):
            with patch("uar.config.config", object()):
                assert _resolve_default_db_path() == "/tmp/env.db"

    def test_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("uar.config.config", object()):
                assert _resolve_default_db_path() == "uar.sqlite3"


class TestLoadDbCorrupted:
    def test_corrupted_object_json(self, tmp_path):
        store = ObjectStore(db_path=str(tmp_path / "test.db"))
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO objects (digest, record_json) VALUES (?, ?)",
                ("bad", "not json"),
            )
            conn.commit()
        store.load_db()
        assert "bad" not in store._objects

    def test_corrupted_lineage_json(self, tmp_path):
        store = ObjectStore(db_path=str(tmp_path / "test.db"))
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO lineage (digest, event_json) VALUES (?, ?)",
                ("bad", "not json"),
            )
            conn.commit()
        store.load_db()
        assert store._lineage.get("bad") == []


class TestDefaultStore:
    def test_set_and_get_default_store(self, tmp_path):
        store = ObjectStore(db_path=str(tmp_path / "test.db"))
        set_default_store(store)
        assert get_default_store() is store
        set_default_store(None)
        # After clearing, get_default_store creates a new one
        new_store = get_default_store()
        assert new_store is not None
        set_default_store(None)
