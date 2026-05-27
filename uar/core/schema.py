"""Schema registry for event and contract validation.

Provides centralized schema versioning and validation for UAR events
to ensure backward compatibility and consistent data structures.
"""

from typing import Any, Dict, List

# Current schema version
CURRENT_EVENT_SCHEMA = "uar.event.v1"

# Required fields per event type
EVENT_SCHEMAS: Dict[str, List[str]] = {
    "start": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
    ],
    "complete": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "payload",
    ],
    "skill_start": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "skill",
    ],
    "skill_complete": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "skill", "payload",
    ],
    "skill_failed": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "skill", "error",
    ],
    "recipe_start": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "payload",
    ],
    "recipe_end": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "payload",
    ],
    "metrics": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "payload",
    ],
    "error": [
        "schema_version", "type", "run_id", "goal_id", "timestamp",
        "error",
    ],
}

# Optional fields that may appear
OPTIONAL_FIELDS = ["correlation_id", "metadata"]


def validate_event(event: Dict[str, Any]) -> List[str]:
    """Validate an event dict against the registered schema.

    Returns a list of validation error messages (empty if valid).
    """
    errors: List[str] = []
    if not isinstance(event, dict):
        errors.append("Event must be a dict")
        return errors

    event_type = event.get("type", "")
    schema_version = event.get("schema_version", "")

    if schema_version != CURRENT_EVENT_SCHEMA:
        errors.append("Unknown schema version")

    required = EVENT_SCHEMAS.get(event_type)
    if required is None:
        errors.append("Unknown event type")
        return errors

    for field in required:
        if field not in event:
            errors.append("Missing required field")

    return errors


def is_valid_event(event: Dict[str, Any]) -> bool:
    """Quick check if an event passes schema validation."""
    return len(validate_event(event)) == 0
