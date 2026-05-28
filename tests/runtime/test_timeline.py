"""Timeline projection validation.

Covers: stable chronology, stable indexing, stable summary metrics.
"""

from __future__ import annotations

from uar.core.timeline import project_timeline, timeline_from_record
from uar.core.replay import run_record_from_events
from uar.core.executor import make_executor_event


class TestStableChronology:
    def test_empty_events(self):
        result = project_timeline([])
        assert result["total_duration_sec"] == 0.0
        assert result["summary"]["status"] == "unknown"

    def test_single_skill_chronology(self):
        evs = [
            make_executor_event("start", "r1", "g1", timestamp=1000.0),
            make_executor_event(
                "skill_start", "r1", "g1", skill="a", timestamp=1000.1,
            ),
            make_executor_event(
                "skill_complete", "r1", "g1", skill="a", timestamp=1000.5,
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "completed"}, timestamp=1001.0,
            ),
        ]
        result = project_timeline(evs)
        assert result["total_duration_sec"] == 1.0
        assert result["skills"][0]["name"] == "a"
        assert result["skills"][0]["duration_sec"] == 0.4

    def test_failed_skill_chronology(self):
        evs = [
            make_executor_event("start", "r1", "g1", timestamp=2000.0),
            make_executor_event(
                "skill_start", "r1", "g1", skill="b", timestamp=2000.1,
            ),
            make_executor_event(
                "skill_failed", "r1", "g1", skill="b", timestamp=2000.3,
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "failed"}, timestamp=2000.5,
            ),
        ]
        result = project_timeline(evs)
        assert result["skills"][0]["status"] == "failed"
        assert result["summary"]["status"] == "failed"


class TestStableIndexing:
    def test_event_types_indexed(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event("complete", "r1", "g1"),
        ]
        result = project_timeline(evs)
        assert result["event_types"] == ["start", "skill_complete", "complete"]

    def test_phases_indexed(self):
        evs = [
            make_executor_event("start", "r1", "g1", timestamp=0.0),
            make_executor_event(
                "skill_start", "r1", "g1", skill="x", timestamp=0.1,
            ),
            make_executor_event(
                "skill_complete", "r1", "g1", skill="x", timestamp=0.5,
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "completed"}, timestamp=1.0,
            ),
        ]
        result = project_timeline(evs)
        assert result["phases"][0]["type"] == "skill"
        assert result["phases"][0]["name"] == "x"


class TestStableSummaryMetrics:
    def test_summary_counts(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_start", "r1", "g1", skill="a"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event("skill_start", "r1", "g1", skill="b"),
            make_executor_event("skill_complete", "r1", "g1", skill="b"),
            make_executor_event("complete", "r1", "g1"),
        ]
        result = project_timeline(evs)
        assert result["summary"]["skill_count"] == 2
        assert result["summary"]["error_count"] == 0

    def test_timeline_from_record(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_start", "r1", "g1", skill="a"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "completed"},
            ),
        ]
        record = run_record_from_events(evs)
        result = timeline_from_record(record)
        assert result["summary"]["skill_count"] == 1
        assert result["summary"]["status"] == "completed"
