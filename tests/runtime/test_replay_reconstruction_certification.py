"""RE-AUDIT SPRINT Ω-2 — C3: Replay Reconstruction Certification.

Validates 4 levels of replay fidelity:
1. Deterministic Replay — same events → same RunRecord
2. Replay Hashing — checkpoint hashes match across replays
3. Adversarial Replay — malformed streams fail loudly
4. Replay Certification Artifact — structured report generation
"""

from __future__ import annotations

import pytest

from uar.core.replay import (
    run_record_from_events,
    hash_event_stream,
    hash_record,
    reconstruct_with_checkpoints,
    certify_replay,
    replay_summary,
)
from uar.core.executor import make_executor_event
from uar.core.exceptions import EventContractError
from uar.core.contracts import RunRecord


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_success_events(run_id="r1", goal_id="g1", skills=None):
    return [
        make_executor_event(
            "start", run_id, goal_id,
            payload={"skills": skills or ["a", "b"]},
        ),
        make_executor_event("skill_complete", run_id, goal_id, skill="a"),
        make_executor_event("skill_complete", run_id, goal_id, skill="b"),
        make_executor_event(
            "complete", run_id, goal_id,
            payload={
                "status": "completed",
                "outputs": [{"skill": "a"}],
                "errors": [],
                "final_context": {"key": "value"},
            },
        ),
    ]


def _make_failure_events(run_id="r1", goal_id="g1", skills=None):
    return [
        make_executor_event(
            "start", run_id, goal_id,
            payload={"skills": skills or ["a"]},
        ),
        make_executor_event(
            "skill_failed", run_id, goal_id,
            skill="a", error="timeout",
        ),
        make_executor_event(
            "complete", run_id, goal_id,
            payload={
                "status": "failed",
                "outputs": [],
                "errors": ["timeout"],
                "final_context": {},
            },
        ),
    ]


def _make_retry_events(run_id="r1", goal_id="g1"):
    return [
        make_executor_event(
            "start", run_id, goal_id,
            payload={"skills": ["a"]},
        ),
        make_executor_event(
            "skill_failed", run_id, goal_id,
            skill="a", error="timeout",
        ),
        make_executor_event(
            "skill_complete", run_id, goal_id, skill="a",
        ),
        make_executor_event(
            "complete", run_id, goal_id,
            payload={
                "status": "completed",
                "outputs": [{"retry": True}],
                "errors": ["timeout"],
                "final_context": {"retried": True},
            },
        ),
    ]


def _make_branching_events(run_id="r1", goal_id="g1"):
    """Simulates a run with conditional skill execution."""
    return [
        make_executor_event(
            "start", run_id, goal_id,
            payload={"skills": ["a", "b", "c"]},
        ),
        make_executor_event("skill_complete", run_id, goal_id, skill="a"),
        make_executor_event("skill_complete", run_id, goal_id, skill="b"),
        make_executor_event(
            "skill_failed", run_id, goal_id,
            skill="c", error="missing",
        ),
        make_executor_event("skill_complete", run_id, goal_id, skill="d"),
        make_executor_event(
            "complete", run_id, goal_id,
            payload={
                "status": "completed",
                "outputs": [{"branch": "fallback"}],
                "errors": ["missing"],
                "final_context": {"path": "fallback_d"},
            },
        ),
    ]


# ------------------------------------------------------------------
# Level 1: Deterministic Replay
# ------------------------------------------------------------------

class TestDeterministicReplay:
    """C3-L1: Same events must always produce the same RunRecord."""

    def test_simple_success_is_deterministic(self):
        evs = _make_success_events()
        r1 = run_record_from_events(evs)
        r2 = run_record_from_events(evs)
        assert hash_record(r1) == hash_record(r2)

    def test_simple_failure_is_deterministic(self):
        evs = _make_failure_events()
        r1 = run_record_from_events(evs)
        r2 = run_record_from_events(evs)
        assert hash_record(r1) == hash_record(r2)

    def test_retry_path_is_deterministic(self):
        evs = _make_retry_events()
        r1 = run_record_from_events(evs)
        r2 = run_record_from_events(evs)
        assert hash_record(r1) == hash_record(r2)
        assert r1.status == "completed"
        assert r1.errors == ["timeout"]

    def test_branching_path_is_deterministic(self):
        evs = _make_branching_events()
        r1 = run_record_from_events(evs)
        r2 = run_record_from_events(evs)
        assert hash_record(r1) == hash_record(r2)
        # Skills come from start payload; dynamically discovered skills
        # (like "d" in this trace) are not currently captured by replay.
        assert r1.skills == ["a", "b", "c"]

    def test_different_run_ids_produce_different_hashes(self):
        evs_a = _make_success_events(run_id="rA")
        evs_b = _make_success_events(run_id="rB")
        r_a = run_record_from_events(evs_a)
        r_b = run_record_from_events(evs_b)
        assert hash_record(r_a) != hash_record(r_b)

    def test_event_stream_hash_is_stable(self):
        evs = _make_success_events()
        h1 = hash_event_stream(evs)
        h2 = hash_event_stream(evs)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_replay_summary_is_stable(self):
        evs = _make_success_events()
        record = run_record_from_events(evs)
        s1 = replay_summary(record)
        s2 = replay_summary(record)
        assert s1 == s2


# ------------------------------------------------------------------
# Level 2: Replay Hashing (Checkpoints)
# ------------------------------------------------------------------

class TestReplayHashing:
    """C3-L2: Checkpoint hashes must match across replays."""

    def test_checkpoint_hashes_are_stable(self):
        evs = _make_success_events()
        cp1 = reconstruct_with_checkpoints(evs)
        cp2 = reconstruct_with_checkpoints(evs)
        assert len(cp1) == len(evs)
        for i in range(len(cp1)):
            assert (
                cp1[i]["accumulated_state_hash"]
                == cp2[i]["accumulated_state_hash"]
            )
            assert cp1[i]["event_hash"] == cp2[i]["event_hash"]

    def test_checkpoint_count_equals_event_count(self):
        evs = _make_branching_events()
        cp = reconstruct_with_checkpoints(evs)
        assert len(cp) == len(evs)

    def test_first_checkpoint_is_start_event(self):
        evs = _make_success_events()
        cp = reconstruct_with_checkpoints(evs)
        assert cp[0]["event_type"] == "start"
        assert cp[0]["index"] == 0

    def test_last_checkpoint_is_complete_event(self):
        evs = _make_success_events()
        cp = reconstruct_with_checkpoints(evs)
        assert cp[-1]["event_type"] == "complete"
        assert cp[-1]["index"] == len(evs) - 1

    def test_checkpoint_hashes_differ_across_positions(self):
        evs = _make_success_events()
        cp = reconstruct_with_checkpoints(evs)
        hashes = [c["accumulated_state_hash"] for c in cp]
        # At least some checkpoints should have different state hashes
        # because state accumulates events
        assert len(set(hashes)) > 1

    def test_failure_path_checkpoint_captures_error(self):
        evs = _make_failure_events()
        cp = reconstruct_with_checkpoints(evs)
        # The skill_failed event should introduce the error
        error_cp = next(c for c in cp if c["event_type"] == "skill_failed")
        assert error_cp["index"] == 1


# ------------------------------------------------------------------
# Level 3: Adversarial Replay
# ------------------------------------------------------------------

class TestAdversarialReplay:
    """C3-L3: Malformed event streams must fail loudly."""

    def test_out_of_order_events_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("complete", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
        ]
        with pytest.raises(EventContractError, match="complete"):
            run_record_from_events(evs)

    def test_duplicate_terminal_event_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("complete", "r1", "g1"),
            make_executor_event("complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError, match="complete"):
            run_record_from_events(evs)

    def test_missing_start_event_rejected(self):
        evs = [
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
            make_executor_event("complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError, match="start"):
            run_record_from_events(evs)

    def test_missing_complete_event_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1", skill="a"),
        ]
        with pytest.raises(EventContractError, match="complete"):
            run_record_from_events(evs)

    def test_empty_stream_rejected(self):
        with pytest.raises(EventContractError, match="empty"):
            run_record_from_events([])

    def test_multiple_run_ids_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("complete", "r2", "g1"),
        ]
        with pytest.raises(EventContractError, match="multiple run_ids"):
            run_record_from_events(evs)

    def test_missing_required_keys_rejected(self):
        evs = [{"type": "start", "run_id": "r1", "goal_id": "g1"}]
        with pytest.raises(EventContractError, match="missing keys"):
            run_record_from_events(evs)

    def test_wrong_schema_version_rejected(self):
        ev = make_executor_event("start", "r1", "g1")
        ev["schema_version"] = "evil"
        with pytest.raises(EventContractError, match="schema"):
            run_record_from_events([ev])

    def test_non_dict_payload_rejected(self):
        ev = make_executor_event("start", "r1", "g1")
        ev["payload"] = "not a dict"
        with pytest.raises(EventContractError, match="payload"):
            run_record_from_events([ev])

    def test_tampered_event_detected_by_hash(self):
        """Modifying an event changes the event stream hash."""
        evs = _make_success_events()
        original_hash = hash_event_stream(evs)
        evs[1]["skill"] = "tampered"
        tampered_hash = hash_event_stream(evs)
        assert tampered_hash != original_hash


# ------------------------------------------------------------------
# Level 4: Replay Certification Artifact
# ------------------------------------------------------------------

class TestReplayCertificationArtifact:
    """C3-L4: Certification report must be complete and accurate."""

    def test_successful_run_certification(self):
        evs = _make_success_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)

        assert report["run_id"] == "r1"
        assert report["certification_version"] == "c3.v1"
        assert report["reconstruction_success"] is True
        assert report["event_count"] == 4
        assert report["state_hash_matches"] is True
        assert report["checkpoint_count"] == 4
        assert report["checkpoint_matches"] is True
        assert report["fidelity_score"] == 100.0
        assert report["replay_duration_ms"] >= 0
        assert "original_hash" in report
        assert "replayed_hash" in report
        assert report["original_hash"] == report["replayed_hash"]

    def test_failure_run_certification(self):
        evs = _make_failure_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)

        assert report["reconstruction_success"] is True
        assert report["state_hash_matches"] is True
        assert report["fidelity_score"] == 100.0

    def test_certification_with_retries(self):
        evs = _make_retry_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)

        assert report["reconstruction_success"] is True
        assert report["fidelity_score"] == 100.0
        assert report["event_count"] == 4

    def test_certification_timestamp_present(self):
        evs = _make_success_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)
        assert isinstance(report["timestamp"], float)
        assert report["timestamp"] > 0

    def test_certification_report_structure(self):
        """Verify all required keys are present in the report."""
        evs = _make_success_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)

        required_keys = {
            "run_id",
            "certification_version",
            "timestamp",
            "reconstruction_success",
            "event_count",
            "replay_duration_ms",
            "state_hash_matches",
            "original_hash",
            "replayed_hash",
            "checkpoint_count",
            "checkpoint_matches",
            "fidelity_score",
        }
        assert required_keys.issubset(report.keys())

    def test_certification_fails_on_invalid_record(self):
        """A record with no events produces a failure report."""
        record = RunRecord(
            run_id="bad",
            goal_id="g1",
            skills=["a"],
            events=[],
        )
        report = certify_replay(record)
        assert report["reconstruction_success"] is False
        assert report["fidelity_score"] == 0.0
        assert "reconstruction_error" in report


# ------------------------------------------------------------------
# Fidelity Score Target
# ------------------------------------------------------------------

class TestReplayFidelityScore:
    """C3: Fidelity score must be 100% for valid replays."""

    def test_fidelity_100_for_success(self):
        evs = _make_success_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)
        assert report["fidelity_score"] == 100.0

    def test_fidelity_100_for_failure(self):
        evs = _make_failure_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)
        assert report["fidelity_score"] == 100.0

    def test_fidelity_100_for_retry(self):
        evs = _make_retry_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)
        assert report["fidelity_score"] == 100.0

    def test_fidelity_100_for_branching(self):
        evs = _make_branching_events()
        record = run_record_from_events(evs)
        report = certify_replay(record)
        assert report["fidelity_score"] == 100.0

    def test_fidelity_0_for_corrupted(self):
        """A record whose events cannot replay gets 0 fidelity."""
        record = RunRecord(
            run_id="bad",
            goal_id="g1",
            skills=["a"],
            events=[
                {"type": "incomplete", "run_id": "bad", "goal_id": "g1"},
            ],
        )
        report = certify_replay(record)
        assert report["fidelity_score"] == 0.0
