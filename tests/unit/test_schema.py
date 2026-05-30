"""Tests for uar.core.schema."""

from uar.core.schema import (
    CURRENT_EVENT_SCHEMA,
    validate_event,
    is_valid_event,
)


class TestValidateEvent:
    def test_non_dict(self):
        errors = validate_event("not a dict")
        assert errors == ["Event must be a dict"]

    def test_unknown_schema_version(self):
        errors = validate_event({
            "schema_version": "v99",
            "type": "skill_start",
            "run_id": "r1",
            "goal_id": "g1",
            "timestamp": 0,
            "payload": {},
        })
        assert any("Unknown schema version" in e for e in errors)

    def test_unknown_event_type(self):
        errors = validate_event({
            "schema_version": CURRENT_EVENT_SCHEMA,
            "type": "unknown_type",
            "run_id": "r1",
            "goal_id": "g1",
            "timestamp": 0,
            "payload": {},
        })
        assert any("Unknown event type" in e for e in errors)

    def test_missing_required_field(self):
        errors = validate_event({
            "schema_version": CURRENT_EVENT_SCHEMA,
            "type": "skill_start",
            "run_id": "r1",
            # missing goal_id, timestamp, payload
        })
        assert any("Missing required field" in e for e in errors)

    def test_valid_event(self):
        errors = validate_event({
            "schema_version": CURRENT_EVENT_SCHEMA,
            "type": "complete",
            "run_id": "r1",
            "goal_id": "g1",
            "timestamp": 0,
            "payload": {},
        })
        assert errors == []


class TestIsValidEvent:
    def test_true(self):
        assert is_valid_event({
            "schema_version": CURRENT_EVENT_SCHEMA,
            "type": "complete",
            "run_id": "r1",
            "goal_id": "g1",
            "timestamp": 0,
            "payload": {},
        }) is True

    def test_false(self):
        assert is_valid_event({}) is False
