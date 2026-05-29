"""Tests for uar.memory.json_store.

Regression coverage for the purge_old_records bug where
``created_at`` was never injected into records.
"""

import json
import time

import pytest

from uar.core.contracts import RunRecord
from uar.memory.json_store import JsonRunStore


@pytest.fixture
def fresh_store(tmp_path):
    """Return a JsonRunStore using a temp directory."""
    store = JsonRunStore(path=str(tmp_path / "runs.jsonl"))
    return store


def _make_record(run_id: str, user_id: str = "u1") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        goal_id="g1",
        skills=["math_compute"],
        status="completed",
        user_id=user_id,
    )


class TestJsonRunStoreAppend:
    def test_append_creates_file(self, fresh_store):
        assert not fresh_store.path.exists()
        fresh_store.append(_make_record("r1"))
        fresh_store.flush()
        assert fresh_store.path.exists()

    def test_append_injects_created_at(self, fresh_store):
        fresh_store.append(_make_record("r1"))
        fresh_store.flush()
        records = fresh_store.list_records()
        assert len(records) == 1
        assert "created_at" in records[0]
        assert isinstance(records[0]["created_at"], (int, float))

    def test_append_many_records(self, fresh_store):
        for i in range(5):
            fresh_store.append(_make_record(f"r{i}"))
        fresh_store.flush()
        assert len(fresh_store.list_records()) == 5


class TestJsonRunStoreList:
    def test_list_records_empty(self, fresh_store):
        assert fresh_store.list_records() == []

    def test_list_records_with_user_filter(self, fresh_store):
        fresh_store.append(_make_record("r1", user_id="alice"))
        fresh_store.append(_make_record("r2", user_id="bob"))
        fresh_store.flush()
        alice = fresh_store.list_records(user_id="alice")
        assert len(alice) == 1
        assert alice[0]["run_id"] == "r1"

    def test_list_all_alias(self, fresh_store):
        fresh_store.append(_make_record("r1"))
        fresh_store.flush()
        assert len(fresh_store.list_all()) == 1

    def test_limit(self, fresh_store):
        for i in range(10):
            fresh_store.append(_make_record(f"r{i}"))
        fresh_store.flush()
        assert len(fresh_store.list_records(limit=3)) == 3

    def test_corrupted_line_skipped(self, fresh_store):
        fresh_store.path.parent.mkdir(parents=True, exist_ok=True)
        fresh_store.path.write_text(
            '{"run_id":"good"}\nnot-json\n{"run_id":"also_good"}\n',
            encoding="utf-8",
        )
        records = fresh_store.list_records()
        assert len(records) == 2
        ids = {r["run_id"] for r in records}
        assert ids == {"good", "also_good"}


class TestJsonRunStoreGetByRunId:
    def test_found(self, fresh_store):
        fresh_store.append(_make_record("find_me"))
        fresh_store.flush()
        result = fresh_store.get_by_run_id("find_me")
        assert result is not None
        assert result["run_id"] == "find_me"

    def test_not_found(self, fresh_store):
        assert fresh_store.get_by_run_id("nope") is None

    def test_returns_latest(self, fresh_store):
        # Append same run_id twice; newest should win
        fresh_store.append(_make_record("dup"))
        time.sleep(0.01)
        fresh_store.append(_make_record("dup"))
        fresh_store.flush()
        result = fresh_store.get_by_run_id("dup")
        assert result is not None


class TestJsonRunStoreDelete:
    def test_delete_removes(self, fresh_store):
        fresh_store.append(_make_record("to_delete"))
        fresh_store.flush()
        assert fresh_store.delete("to_delete") is True
        assert fresh_store.get_by_run_id("to_delete") is None

    def test_delete_not_found(self, fresh_store):
        assert fresh_store.delete("missing") is False


class TestJsonRunStorePurge:
    def test_purge_old_records(self, fresh_store):
        # Manually write records with old and new timestamps
        fresh_store.path.parent.mkdir(parents=True, exist_ok=True)
        old = {"run_id": "old", "created_at": time.time() - 86400 * 10}
        new = {"run_id": "new", "created_at": time.time()}
        fresh_store.path.write_text(
            json.dumps(old) + "\n" + json.dumps(new) + "\n",
            encoding="utf-8",
        )
        removed = fresh_store.purge_old_records(retention_days=5)
        assert removed == 1
        remaining = fresh_store.list_records()
        assert len(remaining) == 1
        assert remaining[0]["run_id"] == "new"

    def test_purge_zero_retention_noop(self, fresh_store):
        assert fresh_store.purge_old_records(0) == 0

    def test_purge_empty_store(self, fresh_store):
        assert fresh_store.purge_old_records(1) == 0

    def test_purge_created_at_missing(self, fresh_store):
        # Records without created_at should be kept (not purged)
        fresh_store.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"run_id": "no_ts"}
        fresh_store.path.write_text(
            json.dumps(record) + "\n",
            encoding="utf-8",
        )
        removed = fresh_store.purge_old_records(retention_days=1)
        assert removed == 0
        assert len(fresh_store.list_records()) == 1


class TestJsonRunStoreBufferFlush:
    def test_buffer_flushed_on_list(self, fresh_store):
        fresh_store.append(_make_record("buf"))
        # Not explicitly flushed; list_records should flush first
        records = fresh_store.list_records()
        assert len(records) == 1

    def test_flush_idempotent(self, fresh_store):
        fresh_store.flush()
        fresh_store.flush()  # no error

    def test_del_triggers_flush(self, fresh_store):
        fresh_store.append(_make_record("del_me"))
        del fresh_store
