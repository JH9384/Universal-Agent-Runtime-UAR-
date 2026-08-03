"""Corpus evaluation for FCRL v4 Evidence Pack validation.

The corpus layer combines reference-relative discrepancy measurement with
ordinary and certificate audits. It remains read-only and accepts already
materialized packs so historical collection and adjudication stay separate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from uar.core.evidence_pack_certificate import (
    EvidencePackAuditComparison,
    compare_evidence_pack_audits,
)
from uar.core.evidence_pack_validation import (
    ValidationArm,
    ValidationTrialResult,
    classify_certificate_leverage,
    evaluate_validation_trial,
)


@dataclass(frozen=True)
class EvidencePackCorpusCase:
    """One blinded or synthetic reference-relative validation case."""

    case_id: str
    reference_name: str
    reference_pack: Mapping[str, Any]
    arms: tuple[ValidationArm, ...]
    provenance: str = "unspecified"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidencePackCorpusArmResult:
    """Semantic discrepancy and validation coverage for one arm."""

    name: str
    audit: EvidencePackAuditComparison

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "audit": self.audit.to_dict()}


@dataclass(frozen=True)
class EvidencePackCorpusCaseResult:
    """Combined result for one corpus case."""

    case_id: str
    provenance: str
    trial: ValidationTrialResult
    classification: str
    audits: tuple[EvidencePackCorpusArmResult, ...]
    notes: tuple[str, ...] = ()

    def audit_by_name(self) -> dict[str, EvidencePackCorpusArmResult]:
        return {item.name: item for item in self.audits}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "provenance": self.provenance,
            "classification": self.classification,
            "trial": self.trial.to_dict(),
            "audits": [item.to_dict() for item in self.audits],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class EvidencePackCorpusResult:
    """Aggregate result for a corpus without suppressing per-case evidence."""

    corpus_id: str
    cases: tuple[EvidencePackCorpusCaseResult, ...] = field(default_factory=tuple)

    @property
    def classification_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case.classification] = counts.get(case.classification, 0) + 1
        return counts

    @property
    def certificate_only_obstruction_count(self) -> int:
        total = 0
        for case in self.cases:
            for arm in case.audits:
                total += len(arm.audit.certificate_only)
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "case_count": len(self.cases),
            "classification_counts": self.classification_counts,
            "certificate_only_obstruction_count": self.certificate_only_obstruction_count,
            "cases": [case.to_dict() for case in self.cases],
        }


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    return value


def _string(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    return value


def corpus_cases_from_document(
    document: Mapping[str, Any],
) -> tuple[str, tuple[EvidencePackCorpusCase, ...]]:
    """Parse a JSON-compatible corpus document into immutable cases."""

    corpus_id = _string(document.get("corpus_id"), path="corpus_id")
    raw_cases = document.get("cases")
    if not isinstance(raw_cases, Sequence) or isinstance(
        raw_cases, (str, bytes, bytearray)
    ):
        raise TypeError("cases must be a sequence")

    cases: list[EvidencePackCorpusCase] = []
    seen: set[str] = set()
    for case_index, raw_case in enumerate(raw_cases):
        case = _mapping(raw_case, path=f"cases/{case_index}")
        case_id = _string(case.get("case_id"), path=f"cases/{case_index}/case_id")
        if case_id in seen:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen.add(case_id)

        reference = _mapping(
            case.get("reference_pack"), path=f"cases/{case_index}/reference_pack"
        )
        raw_arms = case.get("arms")
        if not isinstance(raw_arms, Sequence) or isinstance(
            raw_arms, (str, bytes, bytearray)
        ):
            raise TypeError(f"cases/{case_index}/arms must be a sequence")

        arms: list[ValidationArm] = []
        arm_names: set[str] = set()
        for arm_index, raw_arm in enumerate(raw_arms):
            arm = _mapping(raw_arm, path=f"cases/{case_index}/arms/{arm_index}")
            name = _string(
                arm.get("name"), path=f"cases/{case_index}/arms/{arm_index}/name"
            )
            if name in arm_names:
                raise ValueError(f"duplicate arm {name} in case {case_id}")
            arm_names.add(name)
            pack = _mapping(
                arm.get("pack"), path=f"cases/{case_index}/arms/{arm_index}/pack"
            )
            raw_notes = arm.get("notes") or []
            if not isinstance(raw_notes, Sequence) or isinstance(
                raw_notes, (str, bytes, bytearray)
            ):
                raise TypeError(
                    f"cases/{case_index}/arms/{arm_index}/notes must be a sequence"
                )
            arms.append(
                ValidationArm(
                    name=name,
                    pack=pack,
                    runtime_ms=(
                        float(arm["runtime_ms"])
                        if arm.get("runtime_ms") is not None
                        else None
                    ),
                    storage_bytes=(
                        int(arm["storage_bytes"])
                        if arm.get("storage_bytes") is not None
                        else None
                    ),
                    notes=tuple(str(item) for item in raw_notes),
                )
            )

        required_arms = {"current", "ordinary_validation", "certificate"}
        if arm_names != required_arms:
            missing = sorted(required_arms - arm_names)
            extra = sorted(arm_names - required_arms)
            raise ValueError(
                f"case {case_id} arm set mismatch; missing={missing} extra={extra}"
            )

        raw_notes = case.get("notes") or []
        if not isinstance(raw_notes, Sequence) or isinstance(
            raw_notes, (str, bytes, bytearray)
        ):
            raise TypeError(f"cases/{case_index}/notes must be a sequence")
        cases.append(
            EvidencePackCorpusCase(
                case_id=case_id,
                reference_name=str(case.get("reference_name") or "reference"),
                reference_pack=reference,
                arms=tuple(arms),
                provenance=str(case.get("provenance") or "unspecified"),
                notes=tuple(str(item) for item in raw_notes),
            )
        )

    return corpus_id, tuple(cases)


def evaluate_evidence_pack_corpus(
    *, corpus_id: str, cases: Iterable[EvidencePackCorpusCase]
) -> EvidencePackCorpusResult:
    """Evaluate all cases under identical discrepancy and audit semantics."""

    results: list[EvidencePackCorpusCaseResult] = []
    for case in cases:
        trial = evaluate_validation_trial(
            reference_name=case.reference_name,
            reference_pack=case.reference_pack,
            arms=case.arms,
        )
        audits = tuple(
            EvidencePackCorpusArmResult(
                name=arm.name,
                audit=compare_evidence_pack_audits(arm.pack),
            )
            for arm in case.arms
        )
        results.append(
            EvidencePackCorpusCaseResult(
                case_id=case.case_id,
                provenance=case.provenance,
                trial=trial,
                classification=classify_certificate_leverage(trial),
                audits=audits,
                notes=case.notes,
            )
        )
    return EvidencePackCorpusResult(corpus_id=corpus_id, cases=tuple(results))


def evaluate_evidence_pack_corpus_document(
    document: Mapping[str, Any],
) -> EvidencePackCorpusResult:
    corpus_id, cases = corpus_cases_from_document(document)
    return evaluate_evidence_pack_corpus(corpus_id=corpus_id, cases=cases)


def render_evidence_pack_corpus_report(result: EvidencePackCorpusResult) -> str:
    """Render aggregate and case-level evidence without deleting the vectors."""

    lines = [
        f"# FCRL v4 Corpus Report — {result.corpus_id}",
        "",
        f"- Cases: `{len(result.cases)}`",
        f"- Classifications: `{result.classification_counts}`",
        f"- Certificate-only obstructions: `{result.certificate_only_obstruction_count}`",
        "",
        "| Case | Provenance | Classification | Current | Ordinary | Certificate |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for case in result.cases:
        arms = case.trial.by_name()
        lines.append(
            f"| `{case.case_id}` | `{case.provenance}` | `{case.classification}` | "
            f"{arms['current'].semantic_distance:.6f} | "
            f"{arms['ordinary_validation'].semantic_distance:.6f} | "
            f"{arms['certificate'].semantic_distance:.6f} |"
        )

    for case in result.cases:
        lines.extend(["", f"## {case.case_id}", ""])
        for arm in case.audits:
            lines.append(
                f"- `{arm.name}`: ordinary={len(arm.audit.ordinary.obstructions)} "
                f"certificate={len(arm.audit.certificate.obstructions)} "
                f"certificate_only={len(arm.audit.certificate_only)}"
            )
        if case.notes:
            lines.append(f"- Notes: `{list(case.notes)}`")

    lines.append("")
    return "\n".join(lines)


__all__ = [
    "EvidencePackCorpusArmResult",
    "EvidencePackCorpusCase",
    "EvidencePackCorpusCaseResult",
    "EvidencePackCorpusResult",
    "corpus_cases_from_document",
    "evaluate_evidence_pack_corpus",
    "evaluate_evidence_pack_corpus_document",
    "render_evidence_pack_corpus_report",
]
