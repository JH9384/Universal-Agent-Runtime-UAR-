"""RE-AUDIT SPRINT Ω-4A — Provenance & Authenticity Certification.

Builds on Replay Certification to detect content tampering.

Verdict Matrix:
    Replay PASS + Hash PASS  -> Authentic
    Replay PASS + Hash FAIL  -> Tampered
    Replay FAIL               -> Corrupted
    No Original Hash          -> Unverifiable
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List

from uar.core.executor import make_executor_event
from uar.core.provenance import (
    ProvenanceRecord,
    generate_provenance,
    certify_authenticity,
)
from uar.core.replay import run_record_from_events


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_valid_stream(run_id: str = "prov-test") -> List[Dict[str, Any]]:
    """Create a canonical valid event stream."""
    return [
        make_executor_event(
            "start", run_id, "g1",
            payload={"skills": ["a", "b"]},
        ),
        make_executor_event("skill_complete", run_id, "g1", skill="a"),
        make_executor_event("skill_complete", run_id, "g1", skill="b"),
        make_executor_event(
            "complete", run_id, "g1",
            payload={
                "status": "completed",
                "outputs": [{"ok": True}],
                "errors": [],
                "final_context": {},
            },
        ),
    ]


# ------------------------------------------------------------------
# Ω-4A Tests
# ------------------------------------------------------------------

class TestOmega4AProvenanceGeneration:
    """Test provenance record generation at creation time."""

    def test_generate_provenance_creates_hash(self):
        """ProvenanceRecord contains a non-empty origin hash."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        assert isinstance(prov, ProvenanceRecord)
        assert prov.run_id == record.run_id
        assert len(prov.origin_hash) == 64  # SHA-256 hex = 64 chars
        assert prov.timestamp > 0
        assert prov.certifier == "uar.provenance.v1"
        assert prov.schema_version == "provenance.v1"

    def test_provenance_is_frozen(self):
        """ProvenanceRecord is immutable (frozen dataclass)."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        # Attempt mutation via normal assignment should raise
        try:
            prov.origin_hash = "tampered"
            assert False, "Frozen dataclass should reject mutation"
        except (AttributeError, TypeError, dataclasses.FrozenInstanceError):
            pass  # Expected

    def test_provenance_to_dict_roundtrip(self):
        """ProvenanceRecord serializes to dict correctly."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)
        d = prov.to_dict()

        assert d["run_id"] == prov.run_id
        assert d["origin_hash"] == prov.origin_hash
        assert d["certifier"] == "uar.provenance.v1"


class TestOmega4AAuthenticityVerdicts:
    """Test the four authenticity verdict states."""

    def test_verdict_authentic(self):
        """Replay PASS + Hash PASS -> Authentic."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        cert = certify_authenticity(record, prov)

        assert cert["authenticity_verdict"] == "authentic"
        assert cert["hash_matches"] is True
        assert cert["provenance_available"] is True
        assert cert["replay_certification"]["fidelity_score"] == 100.0
        print(f"\n[Ω-4A] Authentic: {cert['duration_ms']:.2f}ms")

    def test_verdict_tampered_content(self):
        """Replay PASS + Hash FAIL -> Tampered.

        Content mutation (altered payload) keeps replay internal
        consistency but changes the hash.
        """
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        # Tamper: mutate a payload
        record.events[1]["payload"] = {"tampered": True}

        cert = certify_authenticity(record, prov)

        assert cert["authenticity_verdict"] == "tampered"
        assert cert["hash_matches"] is False
        assert cert["replay_certification"]["fidelity_score"] == 100.0
        print(f"\n[Ω-4A] Tampered (content): {cert['duration_ms']:.2f}ms")

    def test_verdict_tampered_structure(self):
        """Mutate structure -> Hash FAIL. May also break replay."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        # Tamper: remove a middle event (changes hash, replay still OK)
        record.events.pop(1)

        cert = certify_authenticity(record, prov)

        # Hash must not match
        assert cert["hash_matches"] is False
        # Verdict is tampered (replay may still pass)
        assert cert["authenticity_verdict"] in ("tampered", "corrupted")
        print(
            f"\n[Ω-4A] Tampered (structure): "
            f"{cert['authenticity_verdict']}, "
            f"{cert['duration_ms']:.2f}ms"
        )

    def test_verdict_corrupted(self):
        """Replay FAIL -> Corrupted (regardless of hash)."""
        record = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(record)

        # Corrupt: invalidate payload type (breaks replay)
        record.events[0]["payload"] = None

        cert = certify_authenticity(record, prov)

        assert cert["authenticity_verdict"] == "corrupted"
        assert cert["replay_certification"]["fidelity_score"] == 0.0
        print(f"\n[Ω-4A] Corrupted: {cert['duration_ms']:.2f}ms")

    def test_verdict_unverifiable(self):
        """No provenance -> Unverifiable (replay-only)."""
        record = run_record_from_events(_make_valid_stream())

        cert = certify_authenticity(record, provenance=None)

        assert cert["authenticity_verdict"] == "unverifiable"
        assert cert["provenance_available"] is False
        assert cert["hash_matches"] is None
        assert cert["origin_hash"] is None
        # But replay still works
        assert cert["replay_certification"]["fidelity_score"] == 100.0
        print(f"\n[Ω-4A] Unverifiable: {cert['duration_ms']:.2f}ms")


class TestOmega4AProvenanceVsReplay:
    """Demonstrate the distinction between the two certifications."""

    def test_replay_cannot_detect_content_tampering(self):
        """Ω-3B discovery: replay alone passes for content mutation."""
        record = run_record_from_events(_make_valid_stream())

        # Mutate payload (content tampering)
        record.events[1]["payload"] = {"tampered": True}

        from uar.core.replay import certify_replay
        replay_cert = certify_replay(record)

        # Replay alone says OK
        assert replay_cert["fidelity_score"] == 100.0

        # But authenticity says TAMPERED
        prov = generate_provenance(
            run_record_from_events(_make_valid_stream())
        )
        auth_cert = certify_authenticity(record, prov)
        assert auth_cert["authenticity_verdict"] == "tampered"

    def test_provenance_detects_what_replay_misses(self):
        """The value add of Ω-4A: detecting mutations replay ignores."""
        # Create original
        original = run_record_from_events(_make_valid_stream())
        prov = generate_provenance(original)

        # Create tampered copy
        tampered = run_record_from_events(_make_valid_stream())
        tampered.events[1]["payload"] = {"tampered": True}

        from uar.core.replay import certify_replay
        replay_original = certify_replay(original)
        replay_tampered = certify_replay(tampered)

        # Both replay as 100% internally consistent
        assert replay_original["fidelity_score"] == 100.0
        assert replay_tampered["fidelity_score"] == 100.0

        # But authenticity distinguishes them
        auth_original = certify_authenticity(original, prov)
        auth_tampered = certify_authenticity(tampered, prov)

        assert auth_original["authenticity_verdict"] == "authentic"
        assert auth_tampered["authenticity_verdict"] == "tampered"
