"""PSERA evidence emission over UAR's existing immutable object/lineage substrate.

Execution produces facts; assessment produces judgments.  This module emits
canonical evidence records but deliberately does not mark controls as passed.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .service import create_record
from .store import ObjectStore

EVIDENCE_SCHEMA = "psera.evidence.contract.v0.1"


def emit_evidence(
    store: ObjectStore,
    *,
    control_id: str,
    claim: str,
    subject: str,
    source: str,
    assessment_method: str,
    result: str,
    authenticity_status: str = "unassessed",
    authority_path: Optional[Iterable[str]] = None,
    policy_version: Optional[str] = None,
    decision: Optional[str] = None,
    effect: Optional[Dict[str, Any]] = None,
    witness_digests: Optional[Iterable[str]] = None,
    limitations: Optional[List[str]] = None,
    owner: Optional[str] = None,
    framework_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Emit an immutable PSERA evidence record.

    ``result`` records an observed fact/result only.  A separate assessment
    layer decides whether that observation satisfies a control requirement.
    """
    witnesses = list(witness_digests or [])
    links = [{"rel": "witness", "target": digest} for digest in witnesses]
    content: Dict[str, Any] = {
        "control_id": control_id,
        "claim": claim,
        "subject": subject,
        "source": source,
        "assessment_method": assessment_method,
        "result": result,
        "authenticity_status": authenticity_status,
        "authority_path": list(authority_path or []),
        "policy_version": policy_version,
        "decision": decision,
        "effect": effect or {},
        "limitations": list(limitations or []),
        "owner": owner,
        "framework_refs": list(framework_refs or []),
    }
    record = create_record(
        store,
        mediaType="application/vnd.psera.evidence+json",
        mode="immutable",
        attributes={
            "schema": EVIDENCE_SCHEMA,
            "agent": "evidence",
            "kind": "control-evidence",
            "control_id": control_id,
            "subject": subject,
        },
        links=links,
        content=content,
    )
    return record


def emit_execution_evidence(
    store: ObjectStore,
    execution: Dict[str, Any],
    *,
    control_id: str = "CTL-04",
    claim: str = "Delegated execution produced a traceable effect",
    subject: str = "uar.execution",
    authority_path: Optional[Iterable[str]] = None,
    policy_version: Optional[str] = None,
    decision: Optional[str] = None,
    limitations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Wrap an existing UAR execution result in a PSERA evidence record."""
    execution_record = execution["executionRecord"]
    output = execution["output"]
    return emit_evidence(
        store,
        control_id=control_id,
        claim=claim,
        subject=subject,
        source="uar.objects.service.execute_runtime",
        assessment_method="Test",
        result=execution.get("status", "unknown"),
        authority_path=authority_path,
        policy_version=policy_version,
        decision=decision,
        effect={
            "output": output,
            "executionRecord": execution_record,
            "runtimeName": execution.get("runtimeName"),
            "runtimeObject": execution.get("runtimeObject"),
        },
        witness_digests=[execution_record, output],
        limitations=limitations,
    )


__all__ = ["EVIDENCE_SCHEMA", "emit_evidence", "emit_execution_evidence"]
