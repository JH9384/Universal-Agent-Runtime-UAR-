"""Unit tests for SqliteRunStore hot data tiering and LRU cache robustness."""

import os
from unittest.mock import patch

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

        # Drain writer queue so SQLite has all records
        store.flush()

        # The hot cache should contain exactly 3 items
        assert len(store._hot_cache) == 3

        # 'run_0' should be evicted as the oldest hot-cache entry.
        assert "run_0" not in store._hot_cache

        # get_by_run_id("run_0") should fall back to SQLite and repopulate
        # the hot cache.
        retrieved = store.get_by_run_id("run_0")
        assert retrieved is not None
        assert retrieved["run_id"] == "run_0"
        assert retrieved["status"] == "completed"

        # Now, 'run_0' is back in the hot cache.
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
    store.flush()

    # Cache hit check
    assert "hot_run" in store._hot_cache

    # Retrieve and verify
    retrieved = store.get_by_run_id("hot_run")
    assert retrieved is not None
    assert retrieved["run_id"] == "hot_run"

    store.close()
