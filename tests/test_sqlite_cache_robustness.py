"""Unit tests for SqliteRunStore hot data tiering and LRU cache robustness."""

import os
from unittest.mock import patch
import pytest

from uar.core.contracts import RunRecord
from uar.memory.sqlite_store import SqliteRunStore


def test_sqlite_hot_cache_eviction_and_fallback(tmp_path):
    # Set hot cache size to 3 for testing LRU eviction
    db_file = str(tmp_path / "test_cache.db")
    with patch.dict(os.environ, {"UAR_HOT_CACHE": "3"}):
        store = SqliteRunStore(db_file)

        # Append 4 records (exceeds hot cache size of 3)
        for i in range(4):
            record = RunRecord(
                run_id=f"run_{i}",
                goal_id=f"goal_{i}",
                skills=[f"skill_{i}"],
                user_id="test_user",
                status="completed",
            )
            store.append(record)

        # The hot cache should contain exactly 3 items
        assert len(store._hot_cache) == 3

        # 'run_0' should have been evicted from the hot cache as it was the oldest
        assert "run_0" not in store._hot_cache

        # However, calling get_by_run_id("run_0") should successfully fall back
        # to SQLite, retrieve the record, and repopulate it back into the hot cache
        retrieved = store.get_by_run_id("run_0")
        assert retrieved is not None
        assert retrieved["run_id"] == "run_0"
        assert retrieved["status"] == "completed"

        # Now, 'run_0' is back in the hot cache, and the oldest item ('run_1') should be evicted if we append again
        assert "run_0" in store._hot_cache
        assert len(store._hot_cache) == 3


def test_sqlite_hot_cache_hit_retrieval(tmp_path):
    db_file = str(tmp_path / "test_hit.db")
    store = SqliteRunStore(db_file)

    record = RunRecord(
        run_id="hot_run",
        goal_id="hot_goal",
        skills=["hot_skill"],
        user_id="test_user",
        status="completed",
    )
    store.append(record)

    # Cache hit check
    assert "hot_run" in store._hot_cache

    # Retrieve and verify
    retrieved = store.get_by_run_id("hot_run")
    assert retrieved is not None
    assert retrieved["run_id"] == "hot_run"
