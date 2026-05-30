"""Tests for uar.memory.base_store."""

from unittest.mock import patch

import pytest

from uar.memory.base_store import run_record_from_dict, get_store


class TestRunRecordFromDict:
    def test_valid(self):
        row = {
            "run_id": "r1",
            "goal_id": "g1",
            "skills": ["s1"],
            "status": "completed",
        }
        rec = run_record_from_dict(row)
        assert rec.run_id == "r1"
        assert rec.goal_id == "g1"
        assert rec.skills == ["s1"]
        assert rec.status == "completed"

    def test_extra_keys_filtered(self):
        row = {
            "run_id": "r1",
            "goal_id": "g1",
            "skills": ["s1"],
            "status": "completed",
            "created_at": 123,
            "id": 42,
            "extra_key": "value",
        }
        rec = run_record_from_dict(row)
        assert rec.run_id == "r1"
        assert not hasattr(rec, "created_at")
        assert not hasattr(rec, "id")
        assert not hasattr(rec, "extra_key")

    def test_missing_required_raises(self):
        row = {"run_id": "r1", "goal_id": "g1"}
        with pytest.raises(TypeError):
            run_record_from_dict(row)

    def test_minimal(self):
        row = {"run_id": "r1", "goal_id": "g1", "skills": []}
        rec = run_record_from_dict(row)
        assert rec.run_id == "r1"
        assert rec.skills == []


class TestGetStore:
    def test_postgres(self):
        with patch.dict(
            "os.environ", {"UAR_DATABASE_URL": "postgres://u@h/d"}
        ):
            with patch("uar.memory.postgres_store.PostgresRunStore") as MockPg:
                MockPg.return_value = "pg_store"
                store = get_store()
        assert store == "pg_store"

    def test_sqlite(self):
        env = {"UAR_SQLITE_PATH": "/tmp/test.db"}
        with patch.dict("os.environ", env, clear=True):
            with patch("uar.memory.sqlite_store.SqliteRunStore") as MockSql:
                MockSql.return_value = "sqlite_store"
                store = get_store()
        assert store == "sqlite_store"

    def test_default_json(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("uar.memory.json_store.JsonRunStore") as MockJson:
                MockJson.return_value = "json_store"
                store = get_store()
        assert store == "json_store"
