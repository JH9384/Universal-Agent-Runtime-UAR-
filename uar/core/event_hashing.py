"""Canonical RuntimeEvent hashing.

Replay equivalence should ignore allowed entropy such as timestamps,
correlation IDs, and regenerated UUID values while preserving semantic event
ordering and payload structure.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List


IGNORED_EVENT_FIELDS = {
    "timestamp",
    "correlation_id",
    "trace_id",
    "span_id",
}


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize RuntimeEvent for deterministic hashing."""
    normalized: Dict[str, Any] = {}
    for key, value in sorted(event.items()):
        if key in IGNORED_EVENT_FIELDS:
            continue
        normalized[key] = value
    return normalized


def canonical_event_hash(event: Dict[str, Any]) -> str:
    """Stable hash for a normalized RuntimeEvent."""
    normalized = normalize_event(event)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def replay_fingerprint(events: Iterable[Dict[str, Any]]) -> str:
    """Stable fingerprint for an ordered RuntimeEvent stream."""
    hashes: List[str] = [canonical_event_hash(ev) for ev in events]
    combined = "|".join(hashes).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()
