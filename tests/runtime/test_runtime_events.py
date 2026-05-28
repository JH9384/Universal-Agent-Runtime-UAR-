"""Runtime event contract validation.

Covers: schema stability, event builder correctness,
metadata separation, enum semantics.
"""

from __future__ import annotations

import time

import pytest

from uar.core.executor import make_executor_event, _event
from uar.core.replay import (
    validate_runtime_event,
    validate_event_stream,
    EVENT_SCHEMA_VERSION,
    REQUIRED_EVENT_KEYS,
)
from uar.core.exceptions import EventContractError


class TestEventSchemaStability:
    def test_required_keys_constant(self):
        assert "schema_version" in REQUIRED_EVENT_KEYS
        assert "type" in REQUIRED_EVENT_KEYS
        assert "run_id" in REQUIRED_EVENT_KEYS
        assert "goal_id" in REQUIRED_EVENT_KEYS
        assert "timestamp" in REQUIRED_EVENT_KEYS
        assert "payload" in REQUIRED_EVENT_KEYS
        assert "error" in REQUIRED_EVENT_KEYS

    def test_schema_version_stable(self):
        assert EVENT_SCHEMA_VERSION == "uar.event.v1"


class TestEventBuilderCorrectness:
    def test_make_executor_event_returns_dict(self):
        ev = make_executor_event("start", "r1", "g1")
        assert isinstance(ev, dict)
        assert ev["schema_version"] == "uar.event.v1"
        assert ev["type"] == "start"
        assert ev["run_id"] == "r1"
        assert ev["goal_id"] == "g1"
        assert "timestamp" in ev

    def test_make_executor_event_with_payload(self):
        ev = make_executor_event(
            "skill_complete", "r1", "g1",
            skill="math_compute",
            payload={"result": 42},
        )
        assert ev["skill"] == "math_compute"
        assert ev["payload"] == {"result": 42}

    def test_legacy_event_alias(self):
        """_event must produce identical output to make_executor_event."""
        ev1 = make_executor_event("start", "r1", "g1", skill="s1")
        ev2 = _event("start", "r1", "g1", skill="s1")
        assert ev1["type"] == ev2["type"]
        assert ev1["run_id"] == ev2["run_id"]
        assert ev1["goal_id"] == ev2["goal_id"]
        assert ev1["skill"] == ev2["skill"]
        assert ev1["payload"] == ev2["payload"]
        assert ev1["error"] == ev2["error"]

    def test_event_timestamp_present(self):
        before = time.time()
        ev = make_executor_event("start", "r1", "g1")
        after = time.time()
        assert before <= ev["timestamp"] <= after


class TestEventValidation:
    def test_valid_event_passes(self):
        ev = make_executor_event("start", "r1", "g1")
        validate_runtime_event(ev)

    def test_missing_key_fails(self):
        ev = {"schema_version": "uar.event.v1", "type": "start"}
        with pytest.raises(EventContractError) as exc:
            validate_runtime_event(ev)
        assert "missing keys" in str(exc.value).lower()

    def test_wrong_schema_version_fails(self):
        ev = make_executor_event("start", "r1", "g1")
        ev["schema_version"] = "uar.event.v2"
        with pytest.raises(EventContractError) as exc:
            validate_runtime_event(ev)
        assert "schema" in str(exc.value).lower()

    def test_payload_must_be_dict(self):
        ev = make_executor_event("start", "r1", "g1")
        ev["payload"] = "not-a-dict"
        with pytest.raises(EventContractError) as exc:
            validate_runtime_event(ev)
        assert "payload" in str(exc.value).lower()

    def test_stream_must_start_with_start(self):
        evs = [
            make_executor_event("skill_complete", "r1", "g1"),
            make_executor_event("complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError) as exc:
            validate_event_stream(evs)
        assert "start" in str(exc.value).lower()

    def test_stream_must_end_with_complete(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("skill_complete", "r1", "g1"),
        ]
        with pytest.raises(EventContractError) as exc:
            validate_event_stream(evs)
        assert "complete" in str(exc.value).lower()

    def test_empty_stream_rejected(self):
        with pytest.raises(EventContractError) as exc:
            validate_event_stream([])
        assert "empty" in str(exc.value).lower()

    def test_multiple_run_ids_rejected(self):
        evs = [
            make_executor_event("start", "r1", "g1"),
            make_executor_event("complete", "r2", "g1"),
        ]
        with pytest.raises(EventContractError) as exc:
            validate_event_stream(evs)
        assert "multiple run_ids" in str(exc.value).lower()


class TestEnumSemantics:
    def test_event_types_are_strings(self):
        ev = make_executor_event("start", "r1", "g1")
        assert isinstance(ev["type"], str)
