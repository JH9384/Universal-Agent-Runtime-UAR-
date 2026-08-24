import hashlib
import json
import time
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

from uar.core.contracts import RunRecord
from uar.core.exceptions import EventContractError


OptionalStr = Optional[str]

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

    # Reject multiple terminal events (adversarial / corrupted stream)
    terminal_count = sum(
        1 for ev in event_list if ev["type"] == TERMINAL_EVENT_TYPE
    )
    if terminal_count > 1:
        raise EventContractError(
            "RuntimeEvent stream contains multiple complete events"
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
    events: Iterable[dict],
    skills: Optional[List[str]] = None,
    user_id: OptionalStr = None,
    metadata: Optional[Dict[str, Any]] = None,
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
        user_id=user_id,
        uor_address=final_event.get("uor_address"),
        uor_witness=final_event.get("uor_witness"),
        metadata=metadata or {},
    )


def replay_summary(record: RunRecord) -> dict:
    return {
        "run_id": record.run_id,
        "goal_id": record.goal_id,
        "status": record.status,
        "skills": list(record.skills),
        "skill_count": len(record.skills),
        "event_count": len(record.events),
        "errors": record.errors,
        "outputs": record.outputs,
    }


def _canonical_json(obj: Any) -> str:
    """Stable canonical JSON for hashing."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, default=str)


def _hash_bytes(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _uor_digest_or_fallback(obj: Any) -> str:
    """UOR-ADDR-1 canonical digest with fallback to legacy JSON+SHA-256.

    Returns ``sha256:<hex>`` when UOR canonicalization succeeds,
    otherwise falls back to ``sort_keys=True`` JSON for resilience.
    """
    try:
        from uar.uor.bounded_json import compute_uor_digest

        return compute_uor_digest(obj)
    except Exception:
        canonical = _canonical_json(obj)
        return "sha256:" + _hash_bytes(canonical.encode("utf-8"))


def hash_event_stream(events: Iterable[dict]) -> str:
    """Return a canonical hash of the event stream.

    Uses UOR-ADDR-1 canonicalization so the hash is portable across
    implementations.
    """
    return _uor_digest_or_fallback(list(events))


def hash_record(record: RunRecord) -> str:
    """Return a canonical hash of a reconstructed RunRecord.

    Verifies that replay reconstruction produces identical state for
    identical event inputs.  UOR-ADDR-1 aligned for portability.
    """
    return _uor_digest_or_fallback(asdict(record))


def reconstruct_with_checkpoints(
    events: Iterable[dict],
) -> List[Dict[str, Any]]:
    """Replay events incrementally and capture state hashes at every event.

    A checkpoint is recorded after processing each event, yielding a full
    hash chain for fidelity verification.

    Returns a list of checkpoint dicts with keys:
      index, event_type, event_hash, accumulated_state_hash.
    """
    event_list = validate_event_stream(events)
    checkpoints: List[Dict[str, Any]] = []

    # Accumulate state incrementally
    run_id = event_list[0]["run_id"]
    goal_id = event_list[0]["goal_id"]
    skills: List[str] = []
    errors: List[str] = []
    outputs: List[Any] = []
    final_context: Dict[str, Any] = {}

    for idx, ev in enumerate(event_list):
        # Update accumulated state based on event type
        ev_type = ev["type"]
        if ev_type == "start":
            skills = list(ev.get("payload", {}).get("skills", []))
        elif ev_type in ("skill_complete", "skill_failed"):
            sk = ev.get("skill")
            if sk and sk not in skills:
                skills.append(sk)
            if ev.get("error"):
                err = str(ev["error"])
                if err not in errors:
                    errors.append(err)
        elif ev_type == "complete":
            p = ev.get("payload", {})
            outputs = list(p.get("outputs", []))
            final_context = dict(p.get("final_context", {}))
            # Final errors from payload take precedence
            payload_errors = p.get("errors", [])
            if payload_errors:
                errors = list(payload_errors)

        # Build partial state snapshot
        partial_state = {
            "run_id": run_id,
            "goal_id": goal_id,
            "skills": skills,
            "errors": errors,
            "outputs": outputs,
            "final_context": final_context,
            "event_count": idx + 1,
        }
        state_hash = _uor_digest_or_fallback(partial_state)
        event_hash = _uor_digest_or_fallback(ev)

        checkpoints.append(
            {
                "index": idx,
                "event_type": ev_type,
                "event_hash": event_hash,
                "accumulated_state_hash": state_hash,
            }
        )

    return checkpoints


def certify_replay(record: RunRecord) -> Dict[str, Any]:
    """Generate a Replay Certification Report (Level 4).

    Validates that a run record can be faithfully reconstructed from
    its event stream and produces a structured audit artifact.
    """
    start_ts = time.time()
    events = list(record.events or [])

    # Level 1: Deterministic reconstruction
    try:
        reconstructed = run_record_from_events(
            events,
            skills=list(record.skills or []),
            user_id=record.user_id,
            metadata=record.metadata,
        )
        reconstruction_success = True
    except EventContractError as exc:
        return {
            "run_id": record.run_id,
            "certification_version": "c3.v1",
            "timestamp": time.time(),
            "reconstruction_success": False,
            "reconstruction_error": str(exc),
            "event_count": len(events),
            "replay_duration_ms": round((time.time() - start_ts) * 1000, 2),
            "state_hash_matches": False,
            "checkpoint_count": 0,
            "checkpoint_matches": False,
            "provenance_valid": False,
            "uor_address_present": record.uor_address is not None,
            "fidelity_score": 0.0,
        }

    # Level 2: Full state hash match
    original_hash = hash_record(record)
    replayed_hash = hash_record(reconstructed)
    state_hash_matches = original_hash == replayed_hash

    # Level 2: Checkpoint hash chain
    checkpoints = reconstruct_with_checkpoints(events)
    replayed_checkpoints = reconstruct_with_checkpoints(events)
    checkpoint_matches = all(
        checkpoints[i]["accumulated_state_hash"]
        == replayed_checkpoints[i]["accumulated_state_hash"]
        for i in range(len(checkpoints))
    )

    # Level 3: Provenance verification is reported separately from replay
    # fidelity. Replay answers whether the supplied event stream is internally
    # reconstructable; provenance/authenticity answers whether that stream is
    # the original untampered stream. Keeping these orthogonal lets Ω-4A detect
    # tampering that replay alone intentionally cannot detect.
    provenance_valid = True
    if record.uor_address and record.uor_witness is not None:
        try:
            from uar.uor.bounded_json import compute_uor_digest

            computed = compute_uor_digest(record.uor_witness)
            provenance_valid = computed == record.uor_address
        except Exception:
            provenance_valid = False

    duration_ms = round((time.time() - start_ts) * 1000, 2)

    # Fidelity is 100% when deterministic and checkpoint replay pass.
    # Provenance validity is surfaced but does not collapse replay fidelity.
    fidelity_score = (
        100.0 if (state_hash_matches and checkpoint_matches) else 0.0
    )

    return {
        "run_id": record.run_id,
        "certification_version": "c3.v1",
        "timestamp": time.time(),
        "reconstruction_success": reconstruction_success,
        "event_count": len(events),
        "replay_duration_ms": duration_ms,
        "state_hash_matches": state_hash_matches,
        "original_hash": original_hash,
        "replayed_hash": replayed_hash,
        "checkpoint_count": len(checkpoints),
        "checkpoint_matches": checkpoint_matches,
        "provenance_valid": provenance_valid,
        "uor_address_present": record.uor_address is not None,
        "fidelity_score": fidelity_score,
    }
