from typing import Iterable, List, Optional

from uar.core.contracts import RunRecord

EVENT_SCHEMA_VERSION = "uar.event.v1"
REQUIRED_EVENT_KEYS = {
    "schema_version",
    "type",
    "run_id",
    "goal_id",
    "skill",
    "timestamp",
    "payload",
    "error",
}
TERMINAL_EVENT_TYPE = "complete"


class EventContractError(ValueError):
    pass


def validate_runtime_event(event: dict) -> None:
    missing = REQUIRED_EVENT_KEYS.difference(event.keys())
    if missing:
        raise EventContractError(
            f"RuntimeEvent missing keys: {sorted(missing)}"
        )
    if event["schema_version"] != EVENT_SCHEMA_VERSION:
        raise EventContractError(
            f"Unsupported RuntimeEvent schema: {event['schema_version']}"
        )
    if not isinstance(event.get("payload"), dict):
        raise EventContractError("RuntimeEvent payload must be a dict")


def validate_event_stream(events: Iterable[dict]) -> list[dict]:
    event_list = list(events)
    if not event_list:
        raise EventContractError("Cannot replay empty event stream")

    for event in event_list:
        validate_runtime_event(event)

    if event_list[0]["type"] != "start":
        raise EventContractError(
            "RuntimeEvent stream must start with a start event"
        )
    if event_list[-1]["type"] != TERMINAL_EVENT_TYPE:
        raise EventContractError(
            "RuntimeEvent stream must end with a complete event"
        )

    run_ids = {event["run_id"] for event in event_list}
    goal_ids = {event["goal_id"] for event in event_list}
    if len(run_ids) != 1:
        raise EventContractError(
            "RuntimeEvent stream contains multiple run_ids"
        )
    if len(goal_ids) != 1:
        raise EventContractError(
            "RuntimeEvent stream contains multiple goal_ids"
        )

    return event_list


def run_record_from_events(
    events: Iterable[dict], skills: Optional[List[str]] = None
) -> RunRecord:
    event_list = validate_event_stream(events)
    start_event = event_list[0]
    final_event = event_list[-1]
    payload = final_event.get("payload", {})

    return RunRecord(
        run_id=start_event["run_id"],
        goal_id=start_event["goal_id"],
        skills=skills or start_event.get("payload", {}).get("skills", []),
        outputs=payload.get("outputs", []),
        status=payload.get("status", "failed"),
        errors=payload.get("errors", []),
        events=event_list,
        final_context=payload.get("final_context", {}),
    )


def replay_summary(record: RunRecord) -> dict:
    return {
        "run_id": record.run_id,
        "goal_id": record.goal_id,
        "status": record.status,
        "skill_count": len(record.skills),
        "event_count": len(record.events),
        "errors": record.errors,
        "outputs": record.outputs,
    }
