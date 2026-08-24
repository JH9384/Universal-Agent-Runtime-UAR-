import base64
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from scripts.semantic_certificate_review import build_report
from uar.core.semantic_certificates import (
    SemanticDecisionCertificate,
    verify_signed_decision_certificate,
)
from uar.core.semantic_trace import (
    CandidateDecision,
    DecisionState,
    SemanticStage,
    SemanticTrace,
)


def _fixture():
    trace = SemanticTrace(
        stages=(
            SemanticStage(
                stage_id="stage-1",
                generated=frozenset({"candidate-1"}),
                decisions=(
                    CandidateDecision(
                        candidate_id="candidate-1",
                        state=DecisionState.ADMIT,
                        certificate_id="cert-1",
                        evidence_refs=("evidence-1",),
                    ),
                ),
                committed="candidate-1",
                terminal=True,
            ),
        ),
        final_result="result-1",
    )
    certificate = SemanticDecisionCertificate(
        certificate_id="cert-1",
        stage_id="stage-1",
        candidate_id="candidate-1",
        decision_state="ADMIT",
        evidence_refs=("evidence-1",),
        final_result="result-1",
        issuer="test-issuer",
        issued_at="2026-08-24T00:00:00+00:00",
    )
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = base64.b64encode(
        private_key.sign(certificate.canonical_bytes())
    ).decode("ascii")
    return trace, certificate, signature, public_key


def test_signed_certificate_verifies_with_public_key_only():
    trace, certificate, signature, public_key = _fixture()

    report = verify_signed_decision_certificate(
        trace, certificate, signature, public_key
    )

    assert report.valid is True
    assert report.reason_codes == ()


def test_tampered_claim_and_wrong_key_are_rejected():
    trace, certificate, signature, public_key = _fixture()
    tampered = replace(certificate, evidence_refs=("different",))
    wrong_key = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    tampered_report = verify_signed_decision_certificate(
        trace, tampered, signature, public_key
    )
    wrong_key_report = verify_signed_decision_certificate(
        trace, certificate, signature, wrong_key
    )

    assert tampered_report.valid is False
    assert set(tampered_report.reason_codes) == {
        "invalid_signature",
        "claim_trace_mismatch",
    }
    assert wrong_key_report.valid is False
    assert wrong_key_report.reason_codes == ("invalid_signature",)


def test_real_executor_signed_certificate_campaign_passes():
    report = build_report()

    assert report["passed"] is True
    assert report["valid_certificate"]["valid"] is True
    assert report["tampered_claim_rejected"] is True
    assert report["wrong_key_rejected"] is True
    assert report["trace_attachment"]["checked_certificates"] == 1
