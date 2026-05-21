"""Unit tests for user-scoped run record storage.

Regression for: row-level privacy in /api/uar/runs endpoint.
"""

from __future__ import annotations

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
