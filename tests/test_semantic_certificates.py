import base64
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from scripts.semantic_certificate_review import build_report
from uar.core.semantic_certificates import (
    SemanticDecisionCertificate,
    verify_ed25519_signature,
    verify_signed_decision_certificate,
)
from uar.core.semantic_trace import (
    CandidateDecision,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    semantic_trace_hash,
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
        constraint_id=None,
        reason_code=None,
        evidence_refs=("evidence-1",),
        committed_candidate_id="candidate-1",
        stage_dependencies=(),
        stage_terminal=True,
        final_result="result-1",
        semantic_trace_hash=semantic_trace_hash(trace),
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


def test_certificate_binds_constraint_reason_and_causal_stage_context():
    trace, certificate, _, public_key = _fixture()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    for tampered in (
        replace(certificate, constraint_id="forged-constraint"),
        replace(certificate, reason_code="forged-reason"),
        replace(certificate, committed_candidate_id=None),
        replace(certificate, stage_dependencies=("forged-stage",)),
        replace(certificate, stage_terminal=False),
        replace(certificate, semantic_trace_hash="forged-trace"),
    ):
        signature = base64.b64encode(
            private_key.sign(tampered.canonical_bytes())
        ).decode("ascii")
        report = verify_signed_decision_certificate(
            trace, tampered, signature, public_key
        )
        assert report.signature_valid is True
        assert report.claim_matches_trace is False
        assert report.valid is False


def test_real_executor_signed_certificate_campaign_passes():
    report = build_report()

    assert report["passed"] is True
    assert report["valid_certificate"]["valid"] is True
    assert report["tampered_claim_rejected"] is True
    assert report["wrong_key_rejected"] is True
    assert report["trace_attachment"]["checked_certificates"] == 1


def test_ed25519_verifier_rejects_ed448_key_and_signature():
    _, certificate, _, _ = _fixture()
    private_key = Ed448PrivateKey.generate()
    signature = base64.b64encode(
        private_key.sign(certificate.canonical_bytes())
    ).decode("ascii")
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    assert verify_ed25519_signature(
        certificate,
        signature,
        public_key,
    ) is False
