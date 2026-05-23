"""Runtime trace fixture certification.

Covers: canonical traces replay deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

from uar.core.replay import (
    run_record_from_events,
    replay_summary,
    validate_event_stream,
)
from uar.core.timeline import timeline_from_record


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list:
    path = FIXTURE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["events"]


class TestRuntimeTraceSuccessFixture:
    def test_fixture_loads(self):
        evs = _load_fixture("runtime_trace_success.json")
        assert len(evs) == 7
        assert evs[0]["type"] == "start"
        assert evs[-1]["type"] == "complete"

    def test_fixture_replay(self):
        evs = _load_fixture("runtime_trace_success.json")
        record = run_record_from_events(evs)
        assert record.status == "completed"
        assert record.errors == []
        assert record.run_id == "run-success-001"

    def test_fixture_timeline(self):
        evs = _load_fixture("runtime_trace_success.json")
        record = run_record_from_events(evs)
        timeline = timeline_from_record(record)
        assert timeline["summary"]["status"] == "completed"
        assert timeline["summary"]["skill_count"] == 2

    def test_fixture_summary(self):
        evs = _load_fixture("runtime_trace_success.json")
        record = run_record_from_events(evs)
        summary = replay_summary(record)
        assert summary["status"] == "completed"
        assert summary["event_count"] == 7

    def test_fixture_event_stream_valid(self):
        evs = _load_fixture("runtime_trace_success.json")
        validated = validate_event_stream(evs)
        assert len(validated) == 7


class TestRuntimeTraceFailureFixture:
    def test_fixture_loads(self):
        evs = _load_fixture("runtime_trace_failure.json")
        assert len(evs) == 6
        assert evs[0]["type"] == "start"
        assert evs[-1]["type"] == "complete"

    def test_fixture_replay(self):
        evs = _load_fixture("runtime_trace_failure.json")
        record = run_record_from_events(evs)
        assert record.status == "failed"
        assert len(record.errors) == 1
        assert record.run_id == "run-failure-001"

    def test_fixture_timeline(self):
        evs = _load_fixture("runtime_trace_failure.json")
        record = run_record_from_events(evs)
        timeline = timeline_from_record(record)
        assert timeline["summary"]["status"] == "failed"
        assert timeline["errors"]

    def test_fixture_summary(self):
        evs = _load_fixture("runtime_trace_failure.json")
        record = run_record_from_events(evs)
        summary = replay_summary(record)
        assert summary["status"] == "failed"
        assert summary["event_count"] == 6

    def test_fixture_event_stream_valid(self):
        evs = _load_fixture("runtime_trace_failure.json")
        validated = validate_event_stream(evs)
        assert len(validated) == 6
