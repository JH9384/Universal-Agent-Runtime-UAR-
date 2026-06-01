"""Governance Layer for UAR.

Ω-4C: Formalize accountability around existing trust primitives.

Current stack:
    Replay Certification
    Authenticity Certification
    Operational Memory

Ω-4C adds:
    Governance Record
    Attestation Layer
    Retention Policies
    Approval Workflow

Completes the lifecycle:
    Event -> Replay -> Authenticity -> Memory -> Governance
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ApprovalState(str, Enum):
    """Simple approval state machine."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class RetentionClass(str, Enum):
    """Retention classification for governance records."""

    NORMAL = "normal"           # 30 days
    CERTIFIED = "certified"     # 1 year
    RECURRING = "recurring"     # permanent
    TAMPERED = "tampered"       # permanent
    GOVERNANCE = "governance"   # permanent


@dataclass
class GovernanceRecord:
    """Comprehensive governance attestation for a single run.

    Combines all certification and intelligence results into
    a single accountable record with retention and approval state.
    """

    run_id: str
    timestamp: float = field(default_factory=time.time)
    schema_version: str = "governance.v1"

    # Certification verdicts
    replay_verdict: str = "unknown"          # from certify_replay
    authenticity_verdict: str = "unknown"    # from certify_authenticity
    certification_fidelity: float = 0.0    # 0.0 - 100.0

    # Operational intelligence tags
    recurrence_tags: List[str] = field(default_factory=list)
    failure_signature: Optional[str] = None
    is_recurring: bool = False

    # Governance state
    retention_class: RetentionClass = RetentionClass.NORMAL
    approval_state: ApprovalState = ApprovalState.PENDING
    approved_by: Optional[str] = None
    approval_timestamp: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "replay_verdict": self.replay_verdict,
            "authenticity_verdict": self.authenticity_verdict,
            "certification_fidelity": self.certification_fidelity,
            "recurrence_tags": self.recurrence_tags,
            "failure_signature": self.failure_signature,
            "is_recurring": self.is_recurring,
            "retention_class": self.retention_class.value,
            "approval_state": self.approval_state.value,
            "approved_by": self.approved_by,
            "approval_timestamp": self.approval_timestamp,
            "notes": self.notes,
        }

    def attest(self) -> str:
        """Generate a compact attestation string.

        Example outputs:
            CERTIFIED AUTHENTIC NON-RECURRING APPROVED
            CERTIFIED TAMPERED RECURRING-FAILURE REVIEW-REQUIRED
            UNVERIFIED CORRUPTED GOVERNANCE-EVENT PENDING
        """
        parts: List[str] = []

        # Replay attestation
        if self.certification_fidelity == 100.0:
            parts.append("CERTIFIED")
        elif self.certification_fidelity == 0.0:
            parts.append("CORRUPTED")
        else:
            parts.append("PARTIAL")

        # Authenticity attestation
        parts.append(self.authenticity_verdict.upper())

        # Recurrence attestation
        if self.is_recurring:
            parts.append("RECURRING-FAILURE")
        elif self.failure_signature:
            parts.append("ISOLATED-FAILURE")
        else:
            parts.append("NON-RECURRING")

        # Approval state
        parts.append(self.approval_state.value.upper().replace("-", "_"))

        return " ".join(parts)

    def transition(self, new_state: ApprovalState, actor: str) -> None:
        """Transition the approval state machine.

        Valid transitions:
            PENDING -> REVIEWED
            REVIEWED -> APPROVED
            REVIEWED -> REJECTED
            Any -> PENDING (reset)
        """
        valid = {
            ApprovalState.PENDING: {ApprovalState.REVIEWED},
            ApprovalState.REVIEWED: {
                ApprovalState.APPROVED, ApprovalState.REJECTED
            },
            ApprovalState.APPROVED: {ApprovalState.PENDING},
            ApprovalState.REJECTED: {ApprovalState.PENDING},
        }
        allowed = valid.get(self.approval_state, set())
        if new_state not in allowed and new_state != self.approval_state:
            raise ValueError(
                f"Invalid transition: {self.approval_state.value} -> "
                f"{new_state.value}"
            )
        self.approval_state = new_state
        self.approved_by = actor
        self.approval_timestamp = time.time()


def classify_retention(
    replay_fidelity: float,
    authenticity_verdict: str,
    is_recurring: bool,
    is_governance_event: bool = False,
) -> RetentionClass:
    """Determine retention class from run characteristics.

    Rules:
        Tampered -> permanent
        Recurring failure -> permanent
        Governance event -> permanent
        Certified + authentic -> 1 year
        Everything else -> 30 days
    """
    if is_governance_event:
        return RetentionClass.GOVERNANCE
    if authenticity_verdict == "tampered":
        return RetentionClass.TAMPERED
    if is_recurring:
        return RetentionClass.RECURRING
    if replay_fidelity == 100.0 and authenticity_verdict == "authentic":
        return RetentionClass.CERTIFIED
    return RetentionClass.NORMAL


def build_governance_record(
    run_id: str,
    replay_cert: Optional[Dict[str, Any]] = None,
    authenticity_cert: Optional[Dict[str, Any]] = None,
    operational_summary: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> GovernanceRecord:
    """Build a GovernanceRecord from certification and intelligence results.

    This is the primary entry point for Ω-4C. It takes the outputs of
    Ω-2 (replay), Ω-4A (authenticity), and Ω-4B (operational memory)
    and produces a single accountable governance record.
    """
    fidelity = 0.0
    replay_verdict = "unknown"
    if replay_cert:
        fidelity = replay_cert.get("fidelity_score", 0.0)
        replay_verdict = "certified" if fidelity == 100.0 else "corrupted"

    auth_verdict = "unverifiable"
    if authenticity_cert:
        auth_verdict = authenticity_cert.get(
            "authenticity_verdict", "unverifiable"
        )

    recurrence_tags: List[str] = []
    is_recurring = False
    failure_sig: Optional[str] = None
    if operational_summary:
        patterns = operational_summary.get("recurring_patterns", [])
        for p in patterns:
            if run_id in p.get("affected_runs", []):
                recurrence_tags.append(p["signature"])
                is_recurring = True
                failure_sig = p["signature"]

    retention = classify_retention(fidelity, auth_verdict, is_recurring)

    record = GovernanceRecord(
        run_id=run_id,
        replay_verdict=replay_verdict,
        authenticity_verdict=auth_verdict,
        certification_fidelity=fidelity,
        recurrence_tags=recurrence_tags,
        failure_signature=failure_sig,
        is_recurring=is_recurring,
        retention_class=retention,
    )

    # Auto-approve fully certified + authentic + non-recurring
    if (
        fidelity == 100.0
        and auth_verdict == "authentic"
        and not is_recurring
    ):
        # System-initiated auto-approval bypasses workflow
        record.approval_state = ApprovalState.APPROVED
        record.approved_by = actor
        record.approval_timestamp = time.time()
        record.notes.append("Auto-approved: fully certified and authentic")

    return record


def summarize_governance(records: List[GovernanceRecord]) -> Dict[str, Any]:
    """Aggregate governance records into an operational summary.

    Useful for dashboards, audit reports, and compliance checks.
    """
    total = len(records)
    if total == 0:
        return {"total_records": 0}

    approved = sum(
        1 for r in records if r.approval_state == ApprovalState.APPROVED
    )
    pending = sum(
        1 for r in records if r.approval_state == ApprovalState.PENDING
    )
    rejected = sum(
        1 for r in records if r.approval_state == ApprovalState.REJECTED
    )
    tampered = sum(
        1 for r in records
        if r.authenticity_verdict == "tampered"
    )
    recurring = sum(1 for r in records if r.is_recurring)
    certified = sum(1 for r in records if r.certification_fidelity == 100.0)

    retention_dist: Dict[str, int] = {}
    for r in records:
        rc = r.retention_class.value
        retention_dist[rc] = retention_dist.get(rc, 0) + 1

    return {
        "total_records": total,
        "approved": approved,
        "pending": pending,
        "rejected": rejected,
        "tampered": tampered,
        "recurring_failures": recurring,
        "fully_certified": certified,
        "certification_rate": certified / total,
        "approval_rate": approved / total,
        "retention_distribution": retention_dist,
        "timestamp": time.time(),
    }
