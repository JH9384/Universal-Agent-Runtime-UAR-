"""Signed decision certificates for Semantic Replay validation.

This module verifies certificate claims with public key material only. It does
not calculate or modify Trust Spine scores.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import asdict, dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from uar.core.semantic_trace import SemanticTrace, semantic_trace_hash

CERTIFICATE_SCHEMA = "uar.semantic-decision-certificate.v1"


@dataclass(frozen=True, slots=True)
class SemanticDecisionCertificate:
    """A signed claim about one observed runtime decision."""

    certificate_id: str
    stage_id: str
    candidate_id: str
    decision_state: str
    constraint_id: str | None
    reason_code: str | None
    evidence_refs: tuple[str, ...]
    committed_candidate_id: str | None
    stage_dependencies: tuple[str, ...]
    stage_terminal: bool
    final_result: str | None
    semantic_trace_hash: str
    issuer: str
    issued_at: str
    schema: str = CERTIFICATE_SCHEMA

    def payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = sorted(self.evidence_refs)
        payload["stage_dependencies"] = sorted(self.stage_dependencies)
        return payload

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CertificateVerificationReport:
    signature_valid: bool
    claim_matches_trace: bool
    valid: bool
    reason_codes: tuple[str, ...]


def verify_ed25519_signature(
    certificate: SemanticDecisionCertificate,
    signature: str,
    public_key_pem: bytes,
) -> bool:
    """Verify an Ed25519 signature using public key material only."""

    try:
        public_key = load_pem_public_key(public_key_pem)
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        signature_bytes = base64.b64decode(signature, validate=True)
        public_key.verify(signature_bytes, certificate.canonical_bytes())
    except (
        AttributeError,
        binascii.Error,
        InvalidSignature,
        TypeError,
        UnsupportedAlgorithm,
        ValueError,
    ):
        return False
    return True


def certificate_claim_matches_trace(
    trace: SemanticTrace,
    certificate: SemanticDecisionCertificate,
) -> bool:
    """Require the signed claim to match its referenced observed decision."""

    if certificate.schema != CERTIFICATE_SCHEMA:
        return False
    if certificate.final_result != trace.final_result:
        return False
    if certificate.semantic_trace_hash != semantic_trace_hash(trace):
        return False
    for stage in trace.stages:
        if stage.stage_id != certificate.stage_id:
            continue
        if certificate.committed_candidate_id != stage.committed:
            return False
        if tuple(sorted(certificate.stage_dependencies)) != tuple(
            sorted(stage.dependencies)
        ):
            return False
        if certificate.stage_terminal is not stage.terminal:
            return False
        for decision in stage.decisions:
            if decision.candidate_id != certificate.candidate_id:
                continue
            return (
                decision.certificate_id == certificate.certificate_id
                and decision.state.value == certificate.decision_state
                and decision.constraint_id == certificate.constraint_id
                and decision.reason_code == certificate.reason_code
                and tuple(sorted(decision.evidence_refs))
                == tuple(sorted(certificate.evidence_refs))
            )
    return False


def verify_signed_decision_certificate(
    trace: SemanticTrace,
    certificate: SemanticDecisionCertificate,
    signature: str,
    public_key_pem: bytes,
) -> CertificateVerificationReport:
    """Verify signature authenticity and semantic claim attachment."""

    signature_valid = verify_ed25519_signature(
        certificate, signature, public_key_pem
    )
    claim_matches_trace = certificate_claim_matches_trace(trace, certificate)
    reasons = []
    if not signature_valid:
        reasons.append("invalid_signature")
    if not claim_matches_trace:
        reasons.append("claim_trace_mismatch")
    return CertificateVerificationReport(
        signature_valid=signature_valid,
        claim_matches_trace=claim_matches_trace,
        valid=signature_valid and claim_matches_trace,
        reason_codes=tuple(reasons),
    )


__all__ = [
    "CERTIFICATE_SCHEMA",
    "CertificateVerificationReport",
    "SemanticDecisionCertificate",
    "certificate_claim_matches_trace",
    "verify_ed25519_signature",
    "verify_signed_decision_certificate",
]
