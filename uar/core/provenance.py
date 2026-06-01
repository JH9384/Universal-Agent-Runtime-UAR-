"""Provenance & Authenticity Certification for UAR.

Builds on Replay Certification (Ω-2/Ω-3) to add content integrity.

Replay Certification answers:
    "Can this event stream be replayed faithfully?"

Authenticity Certification answers:
    "Is this event stream the ORIGINAL event stream?"

Architecture:
    Original Event Stream
            ↓
       SHA-256 (Origin Hash)
            ↓
       Stored Provenance Record
            ↓
       Replay
            ↓
       SHA-256 (Current Hash)
            ↓
       Comparison → Authenticity Verdict

Verdict Matrix:
    Replay PASS + Hash PASS → Authentic
    Replay PASS + Hash FAIL → Tampered
    Replay FAIL              → Corrupted
    No Original Hash         → Unverifiable
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from uar.core.contracts import RunRecord
from uar.core.replay import certify_replay, hash_record


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Immutable provenance attestation for a RunRecord.

    Generated at creation time and stored alongside the record.
    Any content mutation after this point will change the hash
    and be detected by certify_authenticity.
    """

    run_id: str
    origin_hash: str
    timestamp: float
    certifier: str = "uar.provenance.v1"
    schema_version: str = "provenance.v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "origin_hash": self.origin_hash,
            "timestamp": self.timestamp,
            "certifier": self.certifier,
            "schema_version": self.schema_version,
        }


def generate_provenance(record: RunRecord) -> ProvenanceRecord:
    """Generate a ProvenanceRecord from a RunRecord at creation time.

    This should be called immediately after a run is completed,
    before any storage or transmission that could mutate the record.
    """
    return ProvenanceRecord(
        run_id=record.run_id,
        origin_hash=hash_record(record),
        timestamp=time.time(),
    )


def certify_authenticity(
    record: RunRecord,
    provenance: Optional[ProvenanceRecord] = None,
) -> Dict[str, Any]:
    """Generate an Authenticity Certification Report.

    Combines Replay Certification (structural integrity) with
    Provenance Verification (content integrity).

    Args:
        record: The RunRecord to certify.
        provenance: The original ProvenanceRecord. If None,
            the record is unverifiable (replay-only).

    Returns:
        Dict with keys:
            - run_id
            - certification_version
            - timestamp
            - replay_certification: dict (from certify_replay)
            - origin_hash: str or None
            - current_hash: str
            - hash_matches: bool or None
            - authenticity_verdict: str
            - provenance_available: bool
    """
    start_ts = time.time()

    # Step 1: Replay Certification (structural integrity)
    replay_cert = certify_replay(record)

    # Step 2: Compute current hash
    current_hash = hash_record(record)

    # Step 3: Compare to provenance (content integrity)
    if provenance is None:
        return {
            "run_id": record.run_id,
            "certification_version": "provenance.v1",
            "timestamp": time.time(),
            "replay_certification": replay_cert,
            "origin_hash": None,
            "current_hash": current_hash,
            "hash_matches": None,
            "authenticity_verdict": "unverifiable",
            "provenance_available": False,
            "duration_ms": round((time.time() - start_ts) * 1000, 2),
        }

    hash_matches = provenance.origin_hash == current_hash

    # Step 4: Verdict
    replay_pass = replay_cert["fidelity_score"] == 100.0
    if replay_pass and hash_matches:
        verdict = "authentic"
    elif replay_pass and not hash_matches:
        verdict = "tampered"
    elif not replay_pass:
        verdict = "corrupted"
    else:
        verdict = "unknown"

    return {
        "run_id": record.run_id,
        "certification_version": "provenance.v1",
        "timestamp": time.time(),
        "replay_certification": replay_cert,
        "origin_hash": provenance.origin_hash,
        "current_hash": current_hash,
        "hash_matches": hash_matches,
        "authenticity_verdict": verdict,
        "provenance_available": True,
        "duration_ms": round((time.time() - start_ts) * 1000, 2),
    }
