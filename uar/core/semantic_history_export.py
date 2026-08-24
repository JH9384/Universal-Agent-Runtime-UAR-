"""Read-only export of sanitized, explicitly coupled runtime history."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from uar.core.semantic_history import CORPUS_SCHEMA
from uar.core.semantic_trace import SEMANTIC_EVENT_TYPES

EXPORT_MANIFEST_SCHEMA = "uar.semantic-history-export-manifest.v1"
RUNTIME_EVENT_TYPES = frozenset(
    {
        "complete",
        "error",
        "metrics",
        "parallel_complete",
        "parallel_start",
        "parallel_wave",
        "recipe_end",
        "recipe_retry",
        "recipe_skipped",
        "recipe_start",
        "skill_cancelled",
        "skill_complete",
        "skill_failed",
        "skill_retry",
        "skill_start",
        "start",
    }
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _token(key: bytes, namespace: str, value: Any) -> str:
    digest = hmac.new(
        key,
        namespace.encode("utf-8") + b"\0" + _canonical_bytes(value),
        hashlib.sha256,
    ).hexdigest()
    return f"{namespace}:hmac-sha256:{digest}"


def _decode_json_columns(row: dict[str, Any]) -> dict[str, Any]:
    for field in ("skills", "events", "outputs", "metadata", "uor_witness"):
        value = row.get(field)
        if isinstance(value, str):
            try:
                row[field] = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_store_json_{field}") from exc
    return row


def load_run_records(
    path: Path, run_ids: set[str]
) -> dict[str, dict[str, Any]]:
    """Load selected records without constructing a mutating RunStore."""

    if not path.is_file():
        raise ValueError("store_not_found")
    records: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                placeholders = ",".join("?" for _ in run_ids)
                rows = connection.execute(
                    f"SELECT * FROM uar_runs WHERE run_id IN ({placeholders})",
                    tuple(sorted(run_ids)),
                ).fetchall()
        except sqlite3.Error as exc:
            raise ValueError("invalid_sqlite_run_store") from exc
        candidates = [_decode_json_columns(dict(row)) for row in rows]
    else:
        candidates = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"invalid_jsonl_line_{line_number}"
                        ) from exc
                    if not isinstance(row, dict):
                        raise TypeError(f"invalid_jsonl_row_{line_number}")
                    if row.get("run_id") in run_ids:
                        candidates.append(row)
        except UnicodeDecodeError as exc:
            raise ValueError("invalid_jsonl_encoding") from exc

    for row in candidates:
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or run_id not in run_ids:
            continue
        if run_id in records:
            duplicates.add(run_id)
        records[run_id] = row
    if duplicates:
        raise ValueError("duplicate_source_run_id")
    missing = sorted(run_ids - set(records))
    if missing:
        raise ValueError(f"missing_source_run_ids:{','.join(missing)}")
    return records


def _record_snapshot(records: Mapping[str, Mapping[str, Any]]) -> str:
    """Bind the decoded selected rows, including SQLite WAL-visible data."""

    selected = {run_id: records[run_id] for run_id in sorted(records)}
    return f"sha256:{hashlib.sha256(_canonical_bytes(selected)).hexdigest()}"


def _timestamp(value: str) -> float:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid_capture_window") from exc
    if parsed.tzinfo is None:
        raise ValueError("capture_window_timezone_required")
    return parsed.astimezone(timezone.utc).timestamp()


def _annotation(value: Any, key: bytes) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("invalid_semantic_annotation")
    out: dict[str, Any] = {}
    if "state" in value:
        state = str(value["state"]).lower()
        if state not in {"admit", "reject", "defer", "conflict"}:
            raise ValueError("invalid_semantic_state")
        out["state"] = state
    if "committed" in value:
        if not isinstance(value["committed"], bool):
            raise ValueError("invalid_semantic_committed")
        out["committed"] = value["committed"]
    for field in ("constraint_id", "certificate_id", "reason_code"):
        if value.get(field) is not None:
            out[field] = _token(key, field, value[field])
    raw_refs = value.get("evidence_refs")
    if raw_refs is not None:
        if not isinstance(raw_refs, (list, tuple)):
            raise ValueError("invalid_semantic_evidence_refs")
        out["evidence_refs"] = [
            _token(key, "evidence_refs", item) for item in raw_refs
        ]
    raw_calls = value.get("tool_calls")
    if raw_calls is not None:
        if not isinstance(raw_calls, (list, tuple)):
            raise ValueError("invalid_semantic_tool_calls")
        out["tool_calls"] = [
            {"value": _token(key, "tool_calls", item)} for item in raw_calls
        ]
    return out


def sanitize_runtime_events(
    events: Sequence[Any], key: bytes
) -> list[dict[str, Any]]:
    """Retain semantic inputs and replace payload values with HMAC tokens."""

    if len(key) < 32:
        raise ValueError("sanitization_key_too_short")
    sanitized = []
    parallel_execution_seen = False
    for raw in events:
        if not isinstance(raw, Mapping):
            raise TypeError("event_not_object")
        event_type = raw.get("type")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type_invalid")
        if event_type not in RUNTIME_EVENT_TYPES:
            raise ValueError("event_type_not_allowlisted")
        if event_type in {"parallel_start", "parallel_wave"}:
            parallel_execution_seen = True
        event: dict[str, Any] = {"type": event_type, "payload": {}}
        if raw.get("skill") is not None:
            event["skill"] = _token(key, "skill", raw["skill"])
        if raw.get("invocation_id") is not None:
            event["invocation_id"] = _token(
                key, "invocation", raw["invocation_id"]
            )
        payload = raw.get("payload")
        payload = payload if isinstance(payload, Mapping) else {}
        safe_payload: dict[str, Any] = {}
        if event_type == "skill_retry":
            attempt = payload.get("attempt", 0)
            if isinstance(attempt, bool) or not isinstance(attempt, int):
                raise ValueError("invalid_retry_attempt")
            safe_payload["attempt"] = attempt
        elif event_type == "skill_complete":
            result = payload.get("result")
            safe_result: dict[str, Any] = {
                "value": _token(key, "result", result)
            }
            if isinstance(result, Mapping) and "_uar_semantic" in result:
                safe_result["_uar_semantic"] = _annotation(
                    result["_uar_semantic"], key
                )
            safe_payload["result"] = safe_result
            if payload.get("cached") is True:
                safe_payload["cached"] = True
        elif event_type == "complete":
            outputs = payload.get("outputs", [])
            if (
                parallel_execution_seen
                or payload.get("outputs_commutative") is True
            ) and isinstance(outputs, (list, tuple)):
                outputs = sorted(
                    outputs,
                    key=lambda item: _canonical_bytes(item),
                )
            safe_payload = {
                "status": str(payload.get("status", "")),
                "outputs": {"value": _token(key, "outputs", outputs)},
                "final_context": {
                    "value": _token(
                        key, "final-context", payload.get("final_context", {})
                    )
                },
            }
            if payload.get("outputs_commutative") is True:
                safe_payload["outputs_commutative"] = True
        event["payload"] = safe_payload
        sanitized.append(event)
    return sanitized


def _manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("export_manifest_not_object")
    if payload.get("schema") != EXPORT_MANIFEST_SCHEMA:
        raise ValueError("invalid_export_manifest_schema")
    provenance = payload.get("provenance")
    pairs = payload.get("pairs")
    if not isinstance(provenance, dict):
        raise TypeError("missing_export_provenance")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("missing_export_pairs")
    return payload


def export_history_corpus(
    manifest_payload: Any,
    *,
    baseline_store: Path,
    candidate_store: Path,
    sanitization_key: bytes,
) -> dict[str, Any]:
    """Build an unsigned corpus from predeclared source-run coupling."""

    manifest = _manifest(manifest_payload)
    provenance = manifest["provenance"]
    window = provenance.get("capture_window")
    revisions = provenance.get("cohort_revisions")
    reviewed_by = provenance.get("reviewed_by")
    if not isinstance(window, dict):
        raise TypeError("missing_capture_window")
    start = _timestamp(window.get("start"))
    end = _timestamp(window.get("end"))
    if start > end:
        raise ValueError("invalid_capture_window_order")
    if not isinstance(revisions, dict) or not all(
        isinstance(revisions.get(cohort), str) and revisions[cohort]
        for cohort in ("baseline", "candidate")
    ):
        raise ValueError("missing_cohort_revisions")
    if not isinstance(reviewed_by, str) or not reviewed_by:
        raise ValueError("missing_sanitization_reviewer")

    baseline_ids: set[str] = set()
    candidate_ids: set[str] = set()
    pair_ids: set[str] = set()
    for pair in manifest["pairs"]:
        if not isinstance(pair, dict):
            raise TypeError("export_pair_not_object")
        required = (
            "pair_id",
            "split",
            "task_class",
            "final_result_class",
            "baseline_run_id",
            "candidate_run_id",
        )
        if any(
            not isinstance(pair.get(field), str) or not pair[field]
            for field in required
        ):
            raise ValueError("incomplete_export_pair")
        if pair["split"] not in {"calibration", "holdout"}:
            raise ValueError("invalid_export_split")
        if pair["pair_id"] in pair_ids:
            raise ValueError("duplicate_export_pair_id")
        pair_ids.add(pair["pair_id"])
        if (
            pair["baseline_run_id"] in baseline_ids
            or pair["candidate_run_id"] in candidate_ids
        ):
            raise ValueError("source_run_reused")
        baseline_ids.add(pair["baseline_run_id"])
        candidate_ids.add(pair["candidate_run_id"])

    baseline = load_run_records(baseline_store, baseline_ids)
    candidate = load_run_records(candidate_store, candidate_ids)
    runs = []
    for pair in manifest["pairs"]:
        for cohort, records, run_field in (
            ("baseline", baseline, "baseline_run_id"),
            ("candidate", candidate, "candidate_run_id"),
        ):
            record = records[pair[run_field]]
            created_at = record.get("created_at")
            if isinstance(created_at, bool) or not isinstance(
                created_at, (int, float)
            ):
                raise TypeError("missing_source_created_at")
            if not start <= float(created_at) <= end:
                raise ValueError("source_run_outside_capture_window")
            events = record.get("events")
            if not isinstance(events, list) or not events:
                raise ValueError("missing_source_events")
            types = [
                event.get("type")
                for event in events
                if isinstance(event, Mapping)
            ]
            if any(event_type in SEMANTIC_EVENT_TYPES for event_type in types):
                raise ValueError("source_contains_semantic_events")
            if (
                types.count("start") != 1
                or types.count("complete") != 1
                or types[-1:] != ["complete"]
            ):
                raise ValueError("incomplete_source_run")
            run = {
                "run_id": _token(sanitization_key, "run", record["run_id"]),
                "pair_id": _token(sanitization_key, "pair", pair["pair_id"]),
                "split": pair["split"],
                "cohort": cohort,
                "event_mode": "raw_runtime",
                "task_class": pair["task_class"],
                "final_result_class": pair["final_result_class"],
                "events": sanitize_runtime_events(events, sanitization_key),
            }
            if pair.get("case_id") is not None:
                run["case_id"] = _token(
                    sanitization_key, "case", pair["case_id"]
                )
            if pair.get("seed") is not None:
                run["seed"] = pair["seed"]
            runs.append(run)

    snapshots = {
        "baseline": _record_snapshot(baseline),
        "candidate": _record_snapshot(candidate),
    }
    return {
        "schema": CORPUS_SCHEMA,
        "provenance": {
            "source_kind": "observed_operational",
            "model_generated": False,
            "sanitized": True,
            "code_revision": (
                f"baseline={revisions['baseline']};candidate={revisions['candidate']}"
            ),
            "cohort_revisions": revisions,
            "capture_window": window,
            "sanitization": {
                "method": "semantic-allowlist-hmac-sha256-v1",
                "reviewed_by": reviewed_by,
                "source_snapshot": (
                    f"baseline={snapshots['baseline']};candidate={snapshots['candidate']}"
                ),
            },
        },
        "runs": runs,
    }


__all__ = [
    "EXPORT_MANIFEST_SCHEMA",
    "RUNTIME_EVENT_TYPES",
    "export_history_corpus",
    "load_run_records",
    "sanitize_runtime_events",
]
