"""Replay integrity validation.

Covers: deterministic reconstruction, stable event ordering,
proper lifecycle enforcement.
"""

from __future__ import annotations

import pytest

from uar.core.replay import (
    run_record_from_events,
    replay_summary,
)
from uar.core.executor import make_executor_event
from uar.core.exceptions import EventContractError


class TestDeterministicReconstruction:
    def test_success_trace_reconstruction(self):
        evs = [
            make_executor_event(
                "start", "r1", "g1",
                payload={"skills": ["a", "b"]},
            ),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event("skill_complete", "r1", "g1", skill="b"),
            make_executor_event(
                "complete", "r1", "g1",
                payload={
                    "status": "completed",
                    "outputs": [{"skill": "a"}],
                    "errors": [],
                    "final_context": {},
                },
            ),
        ]
        record = run_record_from_events(evs)
        assert record.run_id == "r1"
        assert record.goal_id == "g1"
        assert record.status == "completed"
        assert record.errors == []
        assert len(record.events) == 4

    def test_failure_trace_reconstruction(self):
        evs = [
            make_executor_event(
                "start", "r2", "g2",
                payload={"skills": ["a"]},
            ),
            make_executor_event(
                "skill_failed", "r2", "g2",
                skill="a", error="boom",
            ),
            make_executor_event(
                "complete", "r2", "g2",
                payload={
                    "status": "failed",
                    "outputs": [],
                    "errors": ["boom"],
                    "final_context": {},
                },
            ),
        ]
        record = run_record_from_events(evs)
        assert record.status == "failed"
        assert record.errors == ["boom"]

    def test_skills_extracted_from_start_payload(self):
        evs = [
            make_executor_event(
                "start", "r3", "g3",
                payload={"skills": ["x", "y"]},
            ),
            make_executor_event("complete", "r3", "g3", payload={
                "status": "completed",
                "outputs": [],
                "errors": [],
                "final_context": {},
            }),
        ]
        record = run_record_from_events(evs)
        assert record.skills == ["x", "y"]

    def test_skills_override_from_param(self):
        evs = [
            make_executor_event("start", "r4", "g4"),
            make_executor_event(
                "complete", "r4", "g4",
                payload={
                    "status": "completed",
                    "outputs": [],
                    "errors": [],
                    "final_context": {},
                },
            ),
        ]
        record = run_record_from_events(evs, skills=["z"])
        assert record.skills == ["z"]


class TestStableEventOrdering:
    def test_event_order_preserved(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_start", "r1", "g1", skill="a"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event("complete", "r1", "g1"),
        ]
        record = run_record_from_events(evs)
        types = [e["type"] for e in record.events]
        assert types == ["start", "skill_start", "skill_complete", "complete"]


class TestLifecycleEnforcement:
    def test_missing_start_rejected(self):
        evs = [
            make_executor_event("complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError):
            run_record_from_events(evs)

    def test_missing_complete_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError):
            run_record_from_events(evs)


class TestReplaySummary:
    def test_summary_structure(self):
        evs = [
            make_executor_event(
                "start", "r1", "g1",
                payload={"skills": ["a"]},
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={
                    "status": "completed",
                    "outputs": [],
                    "errors": [],
                    "final_context": {},
                },
            ),
        ]
        record = run_record_from_events(evs)
        summary = replay_summary(record)
        assert summary["run_id"] == "r1"
        assert summary["goal_id"] == "g1"
        assert summary["status"] == "completed"
        assert summary["skill_count"] == 1
        assert summary["event_count"] == 2
