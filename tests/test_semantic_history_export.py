import json
import sqlite3
from datetime import datetime, timezone

import pytest

from uar.core.semantic_history_export import export_history_corpus
from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_trace import semantic_trace_from_events


def _events(run_id, result="private answer"):
    return [
        {
            "type": "start",
            "run_id": run_id,
            "timestamp": 100.0,
            "payload": {"goal": "private goal"},
        },
        {
            "type": "skill_start",
            "skill": "private skill",
            "invocation_id": f"{run_id}:invocation:0",
            "payload": {},
        },
        {
            "type": "skill_complete",
            "skill": "private skill",
            "invocation_id": f"{run_id}:invocation:0",
            "payload": {
                "result": {
                    "answer": result,
                    "_uar_semantic": {
                        "state": "admit",
                        "evidence_refs": ["private evidence"],
                    },
                }
            },
        },
        {
            "type": "complete",
            "payload": {
                "status": "completed",
                "outputs": [result],
                "final_context": {"secret": "private context"},
            },
        },
    ]


def _row(run_id, created_at=1_785_585_600.0):
    return {
        "run_id": run_id,
        "goal_id": "private-goal-id",
        "skills": ["private skill"],
        "events": _events(run_id),
        "outputs": ["private answer"],
        "metadata": {"private": True},
        "status": "completed",
        "created_at": created_at,
    }


def _jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sqlite(path, rows):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE uar_runs (run_id TEXT, goal_id TEXT, skills TEXT, "
            "events TEXT, outputs TEXT, metadata TEXT, status TEXT, "
            "created_at REAL)"
        )
        for row in rows:
            connection.execute(
                "INSERT INTO uar_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["run_id"],
                    row["goal_id"],
                    json.dumps(row["skills"]),
                    json.dumps(row["events"]),
                    json.dumps(row["outputs"]),
                    json.dumps(row["metadata"]),
                    row["status"],
                    row["created_at"],
                ),
            )


def _manifest():
    return {
        "schema": "uar.semantic-history-export-manifest.v1",
        "provenance": {
            "capture_window": {
                "start": "2026-08-01T00:00:00Z",
                "end": "2026-08-02T00:00:00Z",
            },
            "cohort_revisions": {
                "baseline": "git:base",
                "candidate": "git:candidate",
            },
            "reviewed_by": "release-reviewer",
        },
        "pairs": [
            {
                "pair_id": "private-pair",
                "split": "holdout",
                "task_class": "decision",
                "final_result_class": "success",
                "baseline_run_id": "base-raw-id",
                "candidate_run_id": "candidate-raw-id",
            }
        ],
    }


def test_export_reads_jsonl_and_sqlite_and_removes_raw_values(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.db"
    _jsonl(baseline, [_row("base-raw-id")])
    _sqlite(candidate, [_row("candidate-raw-id")])

    corpus = export_history_corpus(
        _manifest(),
        baseline_store=baseline,
        candidate_store=candidate,
        sanitization_key=b"collector-secret-key-material!!1234",
    )

    encoded = json.dumps(corpus)
    assert "private answer" not in encoded
    assert "private goal" not in encoded
    assert "private skill" not in encoded
    assert "private evidence" not in encoded
    assert "base-raw-id" not in encoded
    assert len(corpus["runs"]) == 2
    assert corpus["runs"][0]["pair_id"] == corpus["runs"][1]["pair_id"]
    for run in corpus["runs"]:
        trace = semantic_trace_from_events(
            observe_runtime_semantics(run["events"])
        )
        assert trace.final_result is not None
        assert trace.observation_complete()


def test_export_refuses_posthoc_pair_reuse(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _jsonl(baseline, [_row("base-raw-id")])
    _jsonl(candidate, [_row("candidate-raw-id")])
    manifest = _manifest()
    manifest["pairs"].append(
        {
            **manifest["pairs"][0],
            "pair_id": "second-pair",
        }
    )

    with pytest.raises(ValueError, match="source_run_reused"):
        export_history_corpus(
            manifest,
            baseline_store=baseline,
            candidate_store=candidate,
            sanitization_key=b"collector-secret-key-material!!1234",
        )


def test_export_refuses_incomplete_or_out_of_window_run(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    incomplete = _row("base-raw-id")
    incomplete["events"] = incomplete["events"][:-1]
    _jsonl(baseline, [incomplete])
    _jsonl(candidate, [_row("candidate-raw-id")])

    with pytest.raises(ValueError, match="incomplete_source_run"):
        export_history_corpus(
            _manifest(),
            baseline_store=baseline,
            candidate_store=candidate,
            sanitization_key=b"collector-secret-key-material!!1234",
        )

    _jsonl(baseline, [_row("base-raw-id", created_at=0.0)])
    with pytest.raises(ValueError, match="source_run_outside_capture_window"):
        export_history_corpus(
            _manifest(),
            baseline_store=baseline,
            candidate_store=candidate,
            sanitization_key=b"collector-secret-key-material!!1234",
        )


def test_capture_timestamp_fixture_is_in_declared_window():
    value = datetime.fromtimestamp(1_785_585_600.0, tz=timezone.utc)
    assert value.isoformat().startswith("2026-08-01")


def test_export_refuses_non_allowlisted_event_type(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    row = _row("base-raw-id")
    row["events"].insert(1, {"type": "secret-private-event", "payload": {}})
    _jsonl(baseline, [row])
    _jsonl(candidate, [_row("candidate-raw-id")])

    with pytest.raises(ValueError, match="event_type_not_allowlisted"):
        export_history_corpus(
            _manifest(),
            baseline_store=baseline,
            candidate_store=candidate,
            sanitization_key=b"collector-secret-key-material!!1234",
        )


def test_export_preserves_parallel_output_commutativity(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline_row = _row("base-raw-id")
    candidate_row = _row("candidate-raw-id")
    for row in (baseline_row, candidate_row):
        row["events"].insert(1, {"type": "parallel_start", "payload": {}})
    baseline_row["events"][-1]["payload"]["outputs"] = [
        {"skill": "a"},
        {"skill": "b"},
    ]
    candidate_row["events"][-1]["payload"]["outputs"] = [
        {"skill": "b"},
        {"skill": "a"},
    ]
    _jsonl(baseline, [baseline_row])
    _jsonl(candidate, [candidate_row])

    corpus = export_history_corpus(
        _manifest(),
        baseline_store=baseline,
        candidate_store=candidate,
        sanitization_key=b"collector-secret-key-material!!1234",
    )
    traces = [
        semantic_trace_from_events(observe_runtime_semantics(run["events"]))
        for run in corpus["runs"]
    ]
    assert traces[0].final_result == traces[1].final_result
