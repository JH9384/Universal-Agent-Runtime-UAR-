"""Unit tests for user-scoped run record storage.

Regression for: row-level privacy in /api/uar/runs endpoint.
"""

from __future__ import annotations

import concurrent.futures

from uar.core.contracts import RunRecord
from uar.memory.json_store import JsonRunStore


def test_list_records_filters_by_user_id(tmp_path):
    store = JsonRunStore(str(tmp_path / "runs.jsonl"))

    alice = RunRecord(
        run_id="r1", goal_id="g1", skills=["s1"], user_id="alice"
    )
    bob = RunRecord(
        run_id="r2", goal_id="g2", skills=["s2"], user_id="bob"
    )
    anon = RunRecord(run_id="r3", goal_id="g3", skills=["s3"])

    store.append(alice)
    store.append(bob)
    store.append(anon)

    all_runs = store.list_records()
    assert len(all_runs) == 3

    alice_runs = store.list_records(user_id="alice")
    assert len(alice_runs) == 1
    assert alice_runs[0]["run_id"] == "r1"

    bob_runs = store.list_records(user_id="bob")
    assert len(bob_runs) == 1
    assert bob_runs[0]["run_id"] == "r2"

    # user_id=None returns all records (backward-compatible default)
    anon_runs = store.list_records(user_id=None)
    assert len(anon_runs) == 3


def test_run_record_defaults_user_id_to_none():
    record = RunRecord(run_id="r1", goal_id="g1", skills=["s1"])
    assert record.user_id is None


class TestJsonRunStoreConcurrency:
    """Thread-safety tests for JsonRunStore file locking."""

    def test_concurrent_appends_no_data_loss(self, tmp_path):
        """Many threads appending simultaneously should not lose records."""
        store = JsonRunStore(str(tmp_path / "runs.jsonl"))

        def append_many(start):
            for i in range(20):
                record = RunRecord(
                    run_id=f"r{start}_{i}", goal_id="g1", skills=["s1"]
                )
                store.append(record)
            store.flush()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(append_many, n) for n in range(5)]
            for f in futures:
                f.result()

        records = store.list_records()
        assert len(records) == 100
        run_ids = {r["run_id"] for r in records}
        assert len(run_ids) == 100

    def test_concurrent_reads_while_writing(self, tmp_path):
        """Readers should see consistent state while writers append."""
        store = JsonRunStore(str(tmp_path / "runs.jsonl"))
        record = RunRecord(run_id="r1", goal_id="g1", skills=["s1"])
        store.append(record)
        store.flush()

        def writer():
            for i in range(50):
                r = RunRecord(run_id=f"w{i}", goal_id="g1", skills=["s1"])
                store.append(r)
            store.flush()

        def reader():
            counts = []
            for _ in range(20):
                counts.append(len(store.list_records()))
            return counts

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            writer_future = pool.submit(writer)
            reader_futures = [pool.submit(reader) for _ in range(2)]
            writer_future.result()
            reader_counts = [f.result() for f in reader_futures]

        # Readers should see monotonically non-decreasing counts
        for counts in reader_counts:
            for i in range(1, len(counts)):
                assert counts[i] >= counts[i - 1]

    def test_concurrent_delete_and_read(self, tmp_path):
        """Delete while reading should not corrupt records."""
        store = JsonRunStore(str(tmp_path / "runs.jsonl"))
        for i in range(20):
            store.append(
                RunRecord(run_id=f"r{i}", goal_id="g1", skills=["s1"])
            )
        store.flush()

        def deleter():
            for i in range(10):
                store.delete(f"r{i}")

        def reader():
            for _ in range(10):
                store.list_records()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(deleter), pool.submit(reader)]
            for f in futures:
                f.result()

        # File should still be valid JSONL
        records = store.list_records()
        for r in records:
            assert "run_id" in r

    def test_purge_old_records_concurrent_read(self, tmp_path):
        """Purge while reading should not corrupt records."""
        import time

        store = JsonRunStore(str(tmp_path / "runs.jsonl"))
        for i in range(20):
            store.append(
                RunRecord(run_id=f"r{i}", goal_id="g1", skills=["s1"])
            )
        store.flush()

        # Artificially backdate half the records
        import json
        lines = []
        with store.path.open("r") as f:
            for line in f:
                record = json.loads(line.strip())
                if int(record["run_id"][1:]) < 10:
                    record["created_at"] = time.time() - 86400 * 2
                lines.append(json.dumps(record) + "\n")
        with store.path.open("w") as f:
            f.writelines(lines)

        def purger():
            store.purge_old_records(1)

        def reader():
            for _ in range(10):
                store.list_records()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(purger), pool.submit(reader)]
            for f in futures:
                f.result()

        records = store.list_records()
        for r in records:
            assert "run_id" in r
