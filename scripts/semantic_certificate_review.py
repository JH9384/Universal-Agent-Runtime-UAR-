"""Exercise a signed runtime decision certificate.

Verification uses public key material only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor
from uar.core.registry import registry
from uar.core.semantic_certificates import (
    SemanticDecisionCertificate,
    verify_signed_decision_certificate,
)
from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_trace import (
    semantic_trace_from_events,
    verify_decision_certificates,
)

CERTIFICATE_ID = "omega-7b-runtime-decision-001"
SKILL_NAME = "omega_signed_decision"


def _certified_skill(_):
    return {
        "answer": 42,
        "_uar_semantic": {
            "state": "admit",
            "certificate_id": CERTIFICATE_ID,
            "evidence_refs": ["source:omega-7b-public-evidence"],
        },
    }


def _register_skill() -> None:
    if not registry.is_registered(SKILL_NAME):
        registry.register(SKILL_NAME, _certified_skill)


def build_report() -> dict:
    _register_skill()
    goal = GoalSpec(
        id="semantic-signed-certificate",
        user_intent="verify a signed runtime decision",
        objective="produce a publicly verifiable semantic certificate",
        metadata={"enable_cache": False, "enable_parallel": False},
    )
    strategy = StrategySpec(goal_id=goal.id, ordered_skills=[SKILL_NAME])
    events = tuple(
        Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=2.0,
            _run_id="semantic-signed-certificate-run",
        )
    )
    trace = semantic_trace_from_events(observe_runtime_semantics(events))
    stage = trace.stages[0]
    decision = stage.decisions[0]
    certificate = SemanticDecisionCertificate(
        certificate_id=CERTIFICATE_ID,
        stage_id=stage.stage_id,
        candidate_id=decision.candidate_id,
        decision_state=decision.state.value,
        evidence_refs=decision.evidence_refs,
        final_result=trace.final_result,
        issuer="uar-omega-7b-validation",
        issued_at=datetime.now(timezone.utc).isoformat(),
    )

    private_key = Ed25519PrivateKey.generate()
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = base64.b64encode(
        private_key.sign(certificate.canonical_bytes())
    ).decode("ascii")
    verified = verify_signed_decision_certificate(
        trace, certificate, signature, public_key_pem
    )

    tampered = replace(certificate, decision_state="REJECT")
    tampered_report = verify_signed_decision_certificate(
        trace, tampered, signature, public_key_pem
    )
    wrong_public_key = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    wrong_key_report = verify_signed_decision_certificate(
        trace, certificate, signature, wrong_public_key
    )
    attachment = verify_decision_certificates(
        trace, {CERTIFICATE_ID: verified.valid}
    )
    passed = (
        verified.valid
        and not tampered_report.valid
        and not wrong_key_report.valid
        and attachment.verified
        and attachment.checked_certificates == 1
    )
    return {
        "schema": "uar.semantic-certificate-review.v1",
        "passed": passed,
        "algorithm": "Ed25519",
        "public_key_sha256": hashlib.sha256(public_key_pem).hexdigest(),
        "certificate": certificate.payload(),
        "signature": signature,
        "valid_certificate": {
            "signature_valid": verified.signature_valid,
            "claim_matches_trace": verified.claim_matches_trace,
            "valid": verified.valid,
            "reason_codes": verified.reason_codes,
        },
        "tampered_claim_rejected": not tampered_report.valid,
        "wrong_key_rejected": not wrong_key_report.valid,
        "trace_attachment": {
            "valid": attachment.verified,
            "checked_certificates": attachment.checked_certificates,
            "missing_certificates": attachment.missing_certificates,
            "invalid_certificates": attachment.invalid_certificates,
        },
    }


def main() -> int:
    argparse.ArgumentParser().parse_args()
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
