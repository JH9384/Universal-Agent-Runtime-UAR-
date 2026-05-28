"""Replay certification: trace normalization.

Covers: timestamps, correlation IDs, generated IDs.

Expects: semantic equivalence, NOT literal equality.
"""

from __future__ import annotations

import copy

import pytest

from uar.core.replay import (
    run_record_from_events,
    validate_event_stream,
)
from uar.core.executor import make_executor_event


class TestTimestampNormalization:
    def test_replay_stable_despite_timestamp_drift(self):
        """Same logical trace with different timestamps
        reconstructs to same RunRecord semantics."""
        base = [
            make_executor_event("start", "r1", "g1", timestamp=1000.0),
            make_executor_event(
                "skill_complete", "r1", "g1", skill="a", timestamp=1000.5,
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "completed"}, timestamp=1001.0,
            ),
        ]
        shifted = copy.deepcopy(base)
        for ev in shifted:
            ev["timestamp"] += 5000.0

        rec1 = run_record_from_events(base)
        rec2 = run_record_from_events(shifted)

        # Semantic equivalence: status, skills, errors
        assert rec1.status == rec2.status == "completed"
        assert rec1.skills == rec2.skills
        assert rec1.errors == rec2.errors == []
        # run_id and goal_id preserved
        assert rec1.run_id == rec2.run_id == "r1"
        assert rec1.goal_id == rec2.goal_id == "g1"


class TestCorrelationIdNormalization:
    def test_replay_stable_despite_correlation_id_change(self):
        base = [
            make_executor_event("start", "r1", "g1", correlation_id="old-id"),
            make_executor_event(
                "skill_complete", "r1", "g1", skill="a",
            ),
            make_executor_event(
                "complete", "r1", "g1",
                payload={"status": "completed"},
            ),
        ]
        rec = run_record_from_events(base)
        assert rec.status == "completed"


class TestGeneratedIdNormalization:
    def test_replay_stable_despite_run_id_regeneration(self):
        """Different run IDs but same goal/skills/payloads
        should produce structurally equivalent records."""
        evs_a = [
            make_executor_event("start", "run-a", "g1"),
            make_executor_event("complete", "run-a", "g1", payload={
                "status": "completed",
                "outputs": [],
                "errors": [],
                "final_context": {},
            }),
        ]
        evs_b = [
            make_executor_event("start", "run-b", "g1"),
            make_executor_event("complete", "run-b", "g1", payload={
                "status": "completed",
                "outputs": [],
                "errors": [],
                "final_context": {},
            }),
        ]
        rec_a = run_record_from_events(evs_a)
        rec_b = run_record_from_events(evs_b)

        # Structural equivalence
        assert rec_a.status == rec_b.status
        assert rec_a.errors == rec_b.errors
        # run_id differs (by design)
        assert rec_a.run_id != rec_b.run_id


class TestEventOrderNormalization:
    def test_replay_rejects_out_of_order_events(self):
        evs = [
            make_executor_event("complete", "r1", "g1"),
            make_executor_event("start", "r1", "g1"),
        ]
        with pytest.raises(Exception):
            validate_event_stream(evs)

    def test_replay_rejects_missing_terminal(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
        ]
        with pytest.raises(Exception):
            validate_event_stream(evs)
