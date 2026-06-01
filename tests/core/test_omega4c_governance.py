"""RE-AUDIT SPRINT Ω-4C — Governance Layer.

Formalize accountability around existing trust primitives.

Completes the lifecycle:
    Event -> Replay -> Authenticity -> Memory -> Governance
"""

from __future__ import annotations

from typing import List

from uar.core.governance import (
    ApprovalState,
    RetentionClass,
    GovernanceRecord,
    classify_retention,
    build_governance_record,
    summarize_governance,
)


# ------------------------------------------------------------------
# Ω-4C Tests
# ------------------------------------------------------------------

class TestOmega4CApprovalStateMachine:
    """Test the approval workflow state machine."""

    def test_pending_to_reviewed(self):
        """PENDING -> REVIEWED is valid."""
        rec = GovernanceRecord(run_id="r1")
        assert rec.approval_state == ApprovalState.PENDING

        rec.transition(ApprovalState.REVIEWED, "alice")
        assert rec.approval_state == ApprovalState.REVIEWED
        assert rec.approved_by == "alice"
        assert rec.approval_timestamp is not None

    def test_reviewed_to_approved(self):
        """REVIEWED -> APPROVED is valid."""
        rec = GovernanceRecord(run_id="r1")
        rec.transition(ApprovalState.REVIEWED, "alice")
        rec.transition(ApprovalState.APPROVED, "bob")

        assert rec.approval_state == ApprovalState.APPROVED
        assert rec.approved_by == "bob"

    def test_reviewed_to_rejected(self):
        """REVIEWED -> REJECTED is valid."""
        rec = GovernanceRecord(run_id="r1")
        rec.transition(ApprovalState.REVIEWED, "alice")
        rec.transition(ApprovalState.REJECTED, "bob")

        assert rec.approval_state == ApprovalState.REJECTED

    def test_invalid_transition_blocked(self):
        """PENDING -> APPROVED should be blocked."""
        rec = GovernanceRecord(run_id="r1")

        try:
            rec.transition(ApprovalState.APPROVED, "alice")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid transition" in str(e)

    def test_reset_to_pending(self):
        """APPROVED -> PENDING reset is valid."""
        rec = GovernanceRecord(run_id="r1")
        rec.transition(ApprovalState.REVIEWED, "alice")
        rec.transition(ApprovalState.APPROVED, "bob")
        rec.transition(ApprovalState.PENDING, "system")

        assert rec.approval_state == ApprovalState.PENDING


class TestOmega4CRetentionClassification:
    """Test retention class assignment rules."""

    def test_tampered_permanent(self):
        """Tampered records get permanent retention."""
        rc = classify_retention(
            100.0, "tampered", False
        )
        assert rc == RetentionClass.TAMPERED

    def test_recurring_permanent(self):
        """Recurring failures get permanent retention."""
        rc = classify_retention(
            100.0, "authentic", True
        )
        assert rc == RetentionClass.RECURRING

    def test_certified_one_year(self):
        """Certified + authentic gets 1 year retention."""
        rc = classify_retention(
            100.0, "authentic", False
        )
        assert rc == RetentionClass.CERTIFIED

    def test_governance_event_permanent(self):
        """Governance events override everything."""
        rc = classify_retention(
            0.0, "unverifiable", False, is_governance_event=True
        )
        assert rc == RetentionClass.GOVERNANCE

    def test_default_normal(self):
        """Everything else gets normal (30 day) retention."""
        rc = classify_retention(
            50.0, "authentic", False
        )
        assert rc == RetentionClass.NORMAL


class TestOmega4CAttestation:
    """Test the attestation string generation."""

    def test_attest_certified_authentic(self):
        """Fully certified run produces expected attestation."""
        rec = GovernanceRecord(
            run_id="r1",
            certification_fidelity=100.0,
            authenticity_verdict="authentic",
            approval_state=ApprovalState.APPROVED,
        )
        attestation = rec.attest()

        assert attestation == "CERTIFIED AUTHENTIC NON-RECURRING APPROVED"
        print(f"\n[Ω-4C] Attestation: {attestation}")

    def test_attest_tampered_recurring(self):
        """Tampered recurring failure produces expected attestation."""
        rec = GovernanceRecord(
            run_id="r1",
            certification_fidelity=100.0,
            authenticity_verdict="tampered",
            is_recurring=True,
            failure_signature="timeout::a+b",
            approval_state=ApprovalState.PENDING,
        )
        attestation = rec.attest()

        assert "TAMPERED" in attestation
        assert "RECURRING-FAILURE" in attestation
        assert "PENDING" in attestation
        print(f"\n[Ω-4C] Attestation: {attestation}")

    def test_attest_corrupted(self):
        """Corrupted run produces expected attestation."""
        rec = GovernanceRecord(
            run_id="r1",
            certification_fidelity=0.0,
            authenticity_verdict="corrupted",
            approval_state=ApprovalState.REJECTED,
        )
        attestation = rec.attest()

        assert "CORRUPTED" in attestation
        assert "REJECTED" in attestation
        print(f"\n[Ω-4C] Attestation: {attestation}")


class TestOmega4CGovernanceRecordBuilding:
    """Test building governance records from certification results."""

    def test_build_from_replay_only(self):
        """Can build record with just replay certification."""
        replay_cert = {"fidelity_score": 100.0}
        rec = build_governance_record(
            "r1", replay_cert=replay_cert
        )

        assert rec.run_id == "r1"
        assert rec.certification_fidelity == 100.0
        assert rec.replay_verdict == "certified"
        assert rec.authenticity_verdict == "unverifiable"

    def test_build_auto_approves_certified_authentic(self):
        """Fully certified + authentic runs are auto-approved."""
        replay_cert = {"fidelity_score": 100.0}
        auth_cert = {"authenticity_verdict": "authentic"}
        rec = build_governance_record(
            "r1",
            replay_cert=replay_cert,
            authenticity_cert=auth_cert,
        )

        assert rec.approval_state == ApprovalState.APPROVED
        assert "Auto-approved" in rec.notes[0]
        print(f"\n[Ω-4C] Auto-approved: {rec.attest()}")

    def test_build_flags_recurring(self):
        """Recurring failures are flagged and not auto-approved."""
        replay_cert = {"fidelity_score": 100.0}
        auth_cert = {"authenticity_verdict": "authentic"}
        op_summary = {
            "recurring_patterns": [
                {
                    "signature": "timeout::a+b",
                    "affected_runs": ["r1"],
                }
            ]
        }
        rec = build_governance_record(
            "r1",
            replay_cert=replay_cert,
            authenticity_cert=auth_cert,
            operational_summary=op_summary,
        )

        assert rec.is_recurring is True
        assert rec.approval_state == ApprovalState.PENDING
        assert rec.retention_class == RetentionClass.RECURRING
        print(f"\n[Ω-4C] Recurring flagged: {rec.attest()}")

    def test_build_tampered_retention(self):
        """Tampered records get tampered retention class."""
        replay_cert = {"fidelity_score": 100.0}
        auth_cert = {"authenticity_verdict": "tampered"}
        rec = build_governance_record(
            "r1",
            replay_cert=replay_cert,
            authenticity_cert=auth_cert,
        )

        assert rec.retention_class == RetentionClass.TAMPERED
        assert rec.authenticity_verdict == "tampered"


class TestOmega4CGovernanceSummary:
    """Test aggregate governance summaries."""

    def test_summarize_empty(self):
        """Empty record list produces minimal summary."""
        summary = summarize_governance([])
        assert summary["total_records"] == 0

    def test_summarize_mixed_records(self):
        """Summary captures distribution across states."""
        records: List[GovernanceRecord] = [
            GovernanceRecord(
                run_id="r1",
                certification_fidelity=100.0,
                authenticity_verdict="authentic",
                approval_state=ApprovalState.APPROVED,
            ),
            GovernanceRecord(
                run_id="r2",
                certification_fidelity=100.0,
                authenticity_verdict="tampered",
                approval_state=ApprovalState.PENDING,
            ),
            GovernanceRecord(
                run_id="r3",
                certification_fidelity=0.0,
                authenticity_verdict="corrupted",
                is_recurring=True,
                approval_state=ApprovalState.REJECTED,
            ),
        ]
        summary = summarize_governance(records)

        assert summary["total_records"] == 3
        assert summary["approved"] == 1
        assert summary["pending"] == 1
        assert summary["rejected"] == 1
        assert summary["tampered"] == 1
        assert summary["recurring_failures"] == 1
        assert summary["fully_certified"] == 2
        assert summary["certification_rate"] == 2 / 3
        assert summary["approval_rate"] == 1 / 3
        print(
            f"\n[Ω-4C] Governance summary: "
            f"{summary['total_records']} records, "
            f"{summary['approved']} approved, "
            f"{summary['tampered']} tampered, "
            f"cert_rate={summary['certification_rate']:.0%}"
        )

    def test_summarize_retention_distribution(self):
        """Retention class distribution is captured."""
        records: List[GovernanceRecord] = [
            GovernanceRecord(
                run_id="r1",
                certification_fidelity=100.0,
                authenticity_verdict="authentic",
                retention_class=RetentionClass.CERTIFIED,
            ),
            GovernanceRecord(
                run_id="r2",
                certification_fidelity=100.0,
                authenticity_verdict="tampered",
                retention_class=RetentionClass.TAMPERED,
            ),
        ]
        summary = summarize_governance(records)

        dist = summary["retention_distribution"]
        assert dist["certified"] == 1
        assert dist["tampered"] == 1


class TestOmega4CGovernanceLifecycle:
    """Demonstrate the complete governance lifecycle."""

    def test_lifecycle_certified_authentic(self):
        """Normal run: certified, authentic, auto-approved."""
        replay = {"fidelity_score": 100.0}
        auth = {"authenticity_verdict": "authentic"}
        rec = build_governance_record("r1", replay, auth)

        assert rec.attest() == "CERTIFIED AUTHENTIC NON-RECURRING APPROVED"
        assert rec.retention_class == RetentionClass.CERTIFIED
        print(f"\n[Ω-4C] Lifecycle (normal): {rec.attest()}")

    def test_lifecycle_tampered(self):
        """Tampered run: detected, flagged, pending review."""
        replay = {"fidelity_score": 100.0}
        auth = {"authenticity_verdict": "tampered"}
        rec = build_governance_record("r1", replay, auth)

        assert rec.authenticity_verdict == "tampered"
        assert rec.retention_class == RetentionClass.TAMPERED
        assert rec.approval_state == ApprovalState.PENDING
        print(f"\n[Ω-4C] Lifecycle (tampered): {rec.attest()}")

    def test_lifecycle_recurring_failure(self):
        """Recurring failure: flagged, permanent retention."""
        replay = {"fidelity_score": 100.0}
        auth = {"authenticity_verdict": "authentic"}
        op = {
            "recurring_patterns": [
                {
                    "signature": "timeout::a+b",
                    "affected_runs": ["r1"],
                }
            ]
        }
        rec = build_governance_record("r1", replay, auth, op)

        assert rec.is_recurring is True
        assert rec.retention_class == RetentionClass.RECURRING
        assert "RECURRING-FAILURE" in rec.attest()
        print(f"\n[Ω-4C] Lifecycle (recurring): {rec.attest()}")
