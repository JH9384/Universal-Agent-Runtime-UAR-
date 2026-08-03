"""Read-only comparative validation for UAR Evidence Pack v2.

FCRL v4 freezes the current certificate calculus and asks whether it provides
measurable operational leverage over the existing pipeline and ordinary
validation.  This module supplies the neutral measurement seam.  It does not
change evidence-pack construction, trust, recurrence, certification, or runtime
state.

The comparator deliberately retains a discrepancy vector before reducing it to
one weighted score.  A favorable scalar total must not hide lineage loss,
missing evidence references, or status disagreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class EvidencePackDiscrepancy:
    """Observable differences between a candidate and reference evidence pack."""

    missing_sections: tuple[str, ...] = ()
    extra_sections: tuple[str, ...] = ()
    availability_mismatches: tuple[str, ...] = ()
    status_mismatches: tuple[str, ...] = ()
    missing_evidence_refs: tuple[str, ...] = ()
    extra_evidence_refs: tuple[str, ...] = ()
    missing_run_refs: tuple[str, ...] = ()
    extra_run_refs: tuple[str, ...] = ()
    recurrence_count_abs_error: int = 0
    trust_score_abs_error: float = 0.0

    @property
    def exact(self) -> bool:
        """Whether all declared observables agree exactly."""

        return self.semantic_distance() == 0.0

    def semantic_distance(
        self,
        *,
        section_weight: float = 1.0,
        availability_weight: float = 2.0,
        status_weight: float = 2.0,
        evidence_ref_weight: float = 4.0,
        run_ref_weight: float = 3.0,
        recurrence_weight: float = 1.0,
        trust_weight: float = 1.0,
    ) -> float:
        """Reduce the retained vector to a declared weighted distance.

        The defaults intentionally penalize missing lineage and evidence links
        more strongly than ordinary section-shape differences.  Callers should
        publish any non-default policy weights alongside reported results.
        """

        section_delta = len(self.missing_sections) + len(self.extra_sections)
        evidence_delta = len(self.missing_evidence_refs) + len(
            self.extra_evidence_refs
        )
        run_delta = len(self.missing_run_refs) + len(self.extra_run_refs)
        return float(
            section_weight * section_delta
            + availability_weight * len(self.availability_mismatches)
            + status_weight * len(self.status_mismatches)
            + evidence_ref_weight * evidence_delta
            + run_ref_weight * run_delta
            + recurrence_weight * self.recurrence_count_abs_error
            + trust_weight * self.trust_score_abs_error
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "missing_sections": list(self.missing_sections),
            "extra_sections": list(self.extra_sections),
            "availability_mismatches": list(self.availability_mismatches),
            "status_mismatches": list(self.status_mismatches),
            "missing_evidence_refs": list(self.missing_evidence_refs),
            "extra_evidence_refs": list(self.extra_evidence_refs),
            "missing_run_refs": list(self.missing_run_refs),
            "extra_run_refs": list(self.extra_run_refs),
            "recurrence_count_abs_error": self.recurrence_count_abs_error,
            "trust_score_abs_error": self.trust_score_abs_error,
            "semantic_distance": self.semantic_distance(),
            "exact": self.exact,
        }


@dataclass(frozen=True)
class ValidationArm:
    """One candidate implementation in a comparative validation trial."""

    name: str
    pack: Mapping[str, Any]
    runtime_ms: float | None = None
    storage_bytes: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationArmResult:
    """Measured result for one validation arm."""

    name: str
    discrepancy: EvidencePackDiscrepancy
    runtime_ms: float | None = None
    storage_bytes: int | None = None
    notes: tuple[str, ...] = ()

    @property
    def semantic_distance(self) -> float:
        return self.discrepancy.semantic_distance()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "discrepancy": self.discrepancy.to_dict(),
            "runtime_ms": self.runtime_ms,
            "storage_bytes": self.storage_bytes,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ValidationTrialResult:
    """Reference-relative measurements for all supplied arms."""

    reference_name: str
    arms: tuple[ValidationArmResult, ...] = field(default_factory=tuple)

    def by_name(self) -> Dict[str, ValidationArmResult]:
        return {arm.name: arm for arm in self.arms}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_name": self.reference_name,
            "arms": [arm.to_dict() for arm in self.arms],
        }


def _sections(pack: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for section in pack.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        name = section.get("section")
        if name:
            result[str(name)] = section
    return result


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _walk(child, path + (str(index),))


def _string_set_for_keys(pack: Mapping[str, Any], keys: set[str]) -> set[str]:
    values: set[str] = set()
    for path, value in _walk(pack):
        if not path or path[-1] not in keys:
            continue
        if isinstance(value, str):
            if value and value != "unknown":
                values.add(value)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            values.update(str(item) for item in value if item)
    return values


def _status_map(pack: Mapping[str, Any]) -> Dict[str, str]:
    statuses: Dict[str, str] = {}
    for path, value in _walk(pack):
        if not path or path[-1] not in {"status", "correlation_status"}:
            continue
        if isinstance(value, str):
            statuses["/".join(path)] = value
    return statuses


def _numeric_sum_for_keys(pack: Mapping[str, Any], keys: set[str]) -> float:
    total = 0.0
    for path, value in _walk(pack):
        if path and path[-1] in keys and isinstance(value, (int, float)):
            total += float(value)
    return total


def _numeric_map_for_key(pack: Mapping[str, Any], key: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for path, value in _walk(pack):
        if path and path[-1] == key and isinstance(value, (int, float)):
            values["/".join(path)] = float(value)
    return values


def _absolute_map_error(
    reference: Mapping[str, float], candidate: Mapping[str, float]
) -> float:
    keys = set(reference) | set(candidate)
    return sum(abs(reference.get(key, 0.0) - candidate.get(key, 0.0)) for key in keys)


def compare_evidence_packs(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> EvidencePackDiscrepancy:
    """Compare one candidate Evidence Pack v2 to a declared reference pack."""

    reference_sections = _sections(reference)
    candidate_sections = _sections(candidate)
    reference_names = set(reference_sections)
    candidate_names = set(candidate_sections)

    common_sections = reference_names & candidate_names
    availability_mismatches = tuple(
        sorted(
            name
            for name in common_sections
            if bool(reference_sections[name].get("available", True))
            != bool(candidate_sections[name].get("available", True))
        )
    )

    reference_status = _status_map(reference)
    candidate_status = _status_map(candidate)
    status_mismatches = tuple(
        sorted(
            key
            for key in set(reference_status) | set(candidate_status)
            if reference_status.get(key) != candidate_status.get(key)
        )
    )

    reference_evidence_refs = _string_set_for_keys(reference, {"evidence_refs"})
    candidate_evidence_refs = _string_set_for_keys(candidate, {"evidence_refs"})
    reference_run_refs = _string_set_for_keys(
        reference,
        {
            "run_id",
            "run_ids",
            "affected_run_ids",
            "later_recurrence_run_ids",
            "latest_run_id",
        },
    )
    candidate_run_refs = _string_set_for_keys(
        candidate,
        {
            "run_id",
            "run_ids",
            "affected_run_ids",
            "later_recurrence_run_ids",
            "latest_run_id",
        },
    )

    recurrence_keys = {"recurrence_count", "later_recurrence_count"}
    recurrence_error = int(
        abs(
            _numeric_sum_for_keys(reference, recurrence_keys)
            - _numeric_sum_for_keys(candidate, recurrence_keys)
        )
    )

    trust_error = _absolute_map_error(
        _numeric_map_for_key(reference, "trust_score"),
        _numeric_map_for_key(candidate, "trust_score"),
    )

    return EvidencePackDiscrepancy(
        missing_sections=tuple(sorted(reference_names - candidate_names)),
        extra_sections=tuple(sorted(candidate_names - reference_names)),
        availability_mismatches=availability_mismatches,
        status_mismatches=status_mismatches,
        missing_evidence_refs=tuple(
            sorted(reference_evidence_refs - candidate_evidence_refs)
        ),
        extra_evidence_refs=tuple(
            sorted(candidate_evidence_refs - reference_evidence_refs)
        ),
        missing_run_refs=tuple(sorted(reference_run_refs - candidate_run_refs)),
        extra_run_refs=tuple(sorted(candidate_run_refs - reference_run_refs)),
        recurrence_count_abs_error=recurrence_error,
        trust_score_abs_error=trust_error,
    )


def evaluate_validation_trial(
    *,
    reference_name: str,
    reference_pack: Mapping[str, Any],
    arms: Iterable[ValidationArm],
) -> ValidationTrialResult:
    """Measure current, ordinary-validation, and certificate arms uniformly."""

    results = tuple(
        ValidationArmResult(
            name=arm.name,
            discrepancy=compare_evidence_packs(reference_pack, arm.pack),
            runtime_ms=arm.runtime_ms,
            storage_bytes=arm.storage_bytes,
            notes=arm.notes,
        )
        for arm in arms
    )
    return ValidationTrialResult(reference_name=reference_name, arms=results)


def classify_certificate_leverage(
    result: ValidationTrialResult,
    *,
    current_name: str = "current",
    ordinary_name: str = "ordinary_validation",
    certificate_name: str = "certificate",
) -> str:
    """Classify semantic leverage without hiding the measured vector.

    This deliberately does not claim practical superiority: runtime, storage,
    authoring burden, and reviewer effort must be assessed separately.
    """

    arms = result.by_name()
    current = arms[current_name].semantic_distance
    ordinary = arms[ordinary_name].semantic_distance
    certificate = arms[certificate_name].semantic_distance

    if certificate > ordinary:
        return "negative_leverage"
    if certificate == ordinary:
        return "no_semantic_leverage"
    if certificate == 0.0 and ordinary > 0.0:
        return "exact_reference_reconstruction"
    if certificate < ordinary <= current:
        return "incremental_semantic_leverage"
    return "mixed_semantic_leverage"


def render_validation_report(result: ValidationTrialResult) -> str:
    """Render the retained discrepancy vector and overhead fields as markdown."""

    lines = [
        "# FCRL v4 Evidence Pack Validation",
        "",
        f"Reference: `{result.reference_name}`",
        "",
        "| Arm | Semantic distance | Exact | Runtime ms | Storage bytes |",
        "| --- | ---: | --- | ---: | ---: |",
    ]
    for arm in result.arms:
        runtime = "-" if arm.runtime_ms is None else f"{arm.runtime_ms:.3f}"
        storage = "-" if arm.storage_bytes is None else str(arm.storage_bytes)
        lines.append(
            f"| `{arm.name}` | {arm.semantic_distance:.6f} | "
            f"`{arm.discrepancy.exact}` | {runtime} | {storage} |"
        )

    for arm in result.arms:
        discrepancy = arm.discrepancy
        lines.extend(
            [
                "",
                f"## {arm.name}",
                "",
                f"- Missing sections: `{list(discrepancy.missing_sections)}`",
                f"- Extra sections: `{list(discrepancy.extra_sections)}`",
                f"- Availability mismatches: `{list(discrepancy.availability_mismatches)}`",
                f"- Status mismatches: `{list(discrepancy.status_mismatches)}`",
                f"- Missing evidence refs: `{list(discrepancy.missing_evidence_refs)}`",
                f"- Extra evidence refs: `{list(discrepancy.extra_evidence_refs)}`",
                f"- Missing run refs: `{list(discrepancy.missing_run_refs)}`",
                f"- Extra run refs: `{list(discrepancy.extra_run_refs)}`",
                f"- Recurrence absolute error: `{discrepancy.recurrence_count_abs_error}`",
                f"- Trust-score absolute error: `{discrepancy.trust_score_abs_error}`",
            ]
        )
        if arm.notes:
            lines.append(f"- Notes: `{list(arm.notes)}`")

    lines.append("")
    return "\n".join(lines)


__all__ = [
    "EvidencePackDiscrepancy",
    "ValidationArm",
    "ValidationArmResult",
    "ValidationTrialResult",
    "classify_certificate_leverage",
    "compare_evidence_packs",
    "evaluate_validation_trial",
    "render_validation_report",
]
