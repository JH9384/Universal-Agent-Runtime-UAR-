"""Read-only semantic certificate audit for UAR Evidence Pack v2.

The ordinary audit checks structural application contracts. The certificate audit
checks cross-field evidence obligations that are easy to miss with schema-only
validation. Neither audit mutates the evidence pack or runtime state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

_REQUIRED_SECTIONS = {
    "fleet_signal_evidence",
    "incident_intelligence_evidence",
    "recurrence_correlation_evidence",
}


@dataclass(frozen=True)
class EvidencePackObstruction:
    """One failed structural or semantic obligation."""

    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class EvidencePackAudit:
    """Result of one validation discipline."""

    discipline: str
    obstructions: tuple[EvidencePackObstruction, ...] = ()

    @property
    def admissible(self) -> bool:
        return not self.obstructions

    def codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.obstructions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "discipline": self.discipline,
            "admissible": self.admissible,
            "obstructions": [item.to_dict() for item in self.obstructions],
        }


@dataclass(frozen=True)
class EvidencePackAuditComparison:
    """Ordinary-versus-certificate defect coverage for one candidate pack."""

    ordinary: EvidencePackAudit
    certificate: EvidencePackAudit

    @property
    def certificate_only(self) -> tuple[EvidencePackObstruction, ...]:
        ordinary_keys = {
            (item.code, item.path, item.message) for item in self.ordinary.obstructions
        }
        return tuple(
            item
            for item in self.certificate.obstructions
            if (item.code, item.path, item.message) not in ordinary_keys
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinary": self.ordinary.to_dict(),
            "certificate": self.certificate.to_dict(),
            "certificate_only": [item.to_dict() for item in self.certificate_only],
        }


def _section_entries(pack: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    entries: list[Mapping[str, Any]] = []
    raw = pack.get("sections")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return entries
    for item in raw:
        if isinstance(item, Mapping):
            entries.append(item)
    return entries


def _sections(pack: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in _section_entries(pack):
        name = item.get("section")
        if isinstance(name, str) and name:
            result[name] = item
    return result


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    counts = Counter(values)
    return tuple(sorted(value for value, count in counts.items() if count > 1))


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _obstruction(code: str, path: str, message: str) -> EvidencePackObstruction:
    return EvidencePackObstruction(code=code, path=path, message=message)


def audit_evidence_pack_ordinary(pack: Mapping[str, Any]) -> EvidencePackAudit:
    """Check conventional shape, required sections, and primitive value ranges."""

    issues: list[EvidencePackObstruction] = []
    if pack.get("version") != "v2":
        issues.append(
            _obstruction("invalid_version", "version", "Evidence Pack version must be v2")
        )

    entries = _section_entries(pack)
    names = [
        str(item.get("section"))
        for item in entries
        if isinstance(item.get("section"), str) and item.get("section")
    ]
    if not isinstance(pack.get("sections"), Sequence) or isinstance(
        pack.get("sections"), (str, bytes, bytearray)
    ):
        issues.append(
            _obstruction("sections_not_sequence", "sections", "sections must be a sequence")
        )

    for name in sorted(_REQUIRED_SECTIONS - set(names)):
        issues.append(
            _obstruction(
                "missing_required_section",
                f"sections/{name}",
                f"required section {name} is missing",
            )
        )

    for name in _duplicates(names):
        issues.append(
            _obstruction(
                "duplicate_section",
                f"sections/{name}",
                f"section {name} occurs more than once",
            )
        )

    for index, item in enumerate(entries):
        if not isinstance(item.get("section"), str) or not item.get("section"):
            issues.append(
                _obstruction(
                    "missing_section_name",
                    f"sections/{index}/section",
                    "section name must be a non-empty string",
                )
            )
        if "available" in item and not isinstance(item.get("available"), bool):
            issues.append(
                _obstruction(
                    "invalid_availability",
                    f"sections/{index}/available",
                    "available must be boolean when supplied",
                )
            )

    def walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
        yield path, value
        if isinstance(value, Mapping):
            for key, child in value.items():
                yield from walk(child, path + (str(key),))
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for index, child in enumerate(value):
                yield from walk(child, path + (str(index),))

    for path, value in walk(pack):
        if path and path[-1] == "trust_score" and isinstance(value, (int, float)):
            if not 0.0 <= float(value) <= 1.0:
                issues.append(
                    _obstruction(
                        "trust_score_out_of_range",
                        "/".join(path),
                        "trust score must be in [0,1]",
                    )
                )

    return EvidencePackAudit("ordinary_validation", tuple(issues))


def audit_evidence_pack_certificate(pack: Mapping[str, Any]) -> EvidencePackAudit:
    """Check structural contracts plus cross-field lineage and recurrence obligations."""

    issues = list(audit_evidence_pack_ordinary(pack).obstructions)
    sections = _sections(pack)

    correlation = sections.get("recurrence_correlation_evidence")
    if correlation is not None:
        correlations_raw = correlation.get("correlations")
        correlations = (
            list(correlations_raw)
            if isinstance(correlations_raw, Sequence)
            and not isinstance(correlations_raw, (str, bytes, bytearray))
            else []
        )
        available = bool(correlation.get("available", bool(correlations)))
        if available and not correlations:
            issues.append(
                _obstruction(
                    "available_without_correlation_evidence",
                    "sections/recurrence_correlation_evidence",
                    "available correlation section must contain correlation evidence",
                )
            )
        if not available and correlations:
            issues.append(
                _obstruction(
                    "unavailable_with_correlation_evidence",
                    "sections/recurrence_correlation_evidence",
                    "unavailable correlation section cannot carry active correlations",
                )
            )

        for index, raw in enumerate(correlations):
            if not isinstance(raw, Mapping):
                issues.append(
                    _obstruction(
                        "invalid_correlation_record",
                        f"sections/recurrence_correlation_evidence/correlations/{index}",
                        "correlation record must be an object",
                    )
                )
                continue
            base = f"sections/recurrence_correlation_evidence/correlations/{index}"
            run_id = raw.get("run_id")
            later_runs = _as_string_list(raw.get("later_recurrence_run_ids"))
            evidence_refs = _as_string_list(raw.get("evidence_refs"))
            declared_count = raw.get("later_recurrence_count")

            if isinstance(declared_count, int) and declared_count != len(later_runs):
                issues.append(
                    _obstruction(
                        "recurrence_count_mismatch",
                        f"{base}/later_recurrence_count",
                        "later recurrence count must equal retained later run references",
                    )
                )

            for duplicate in _duplicates(later_runs):
                issues.append(
                    _obstruction(
                        "duplicate_later_run_reference",
                        f"{base}/later_recurrence_run_ids",
                        f"later run {duplicate} occurs more than once",
                    )
                )
            for duplicate in _duplicates(evidence_refs):
                issues.append(
                    _obstruction(
                        "duplicate_evidence_reference",
                        f"{base}/evidence_refs",
                        f"evidence reference {duplicate} occurs more than once",
                    )
                )

            required_refs = {f"run:{item}" for item in later_runs}
            if isinstance(run_id, str) and run_id and run_id != "unknown":
                required_refs.add(f"run:{run_id}")
            for missing in sorted(required_refs - set(evidence_refs)):
                issues.append(
                    _obstruction(
                        "missing_correlation_lineage",
                        f"{base}/evidence_refs",
                        f"required evidence reference {missing} is absent",
                    )
                )

            status = raw.get("correlation_status")
            if status == "no_later_recurrence" and later_runs:
                issues.append(
                    _obstruction(
                        "status_recurrence_conflict",
                        f"{base}/correlation_status",
                        "no_later_recurrence conflicts with retained later run references",
                    )
                )
            if status == "later_recurrence" and not later_runs:
                issues.append(
                    _obstruction(
                        "status_recurrence_conflict",
                        f"{base}/correlation_status",
                        "later_recurrence requires at least one later run reference",
                    )
                )

    incident = sections.get("incident_intelligence_evidence")
    if incident is not None:
        summary = incident.get("summary")
        patterns = summary.get("patterns") if isinstance(summary, Mapping) else []
        if isinstance(patterns, Sequence) and not isinstance(
            patterns, (str, bytes, bytearray)
        ):
            for index, raw in enumerate(patterns):
                if not isinstance(raw, Mapping):
                    continue
                base = f"sections/incident_intelligence_evidence/summary/patterns/{index}"
                affected = _as_string_list(raw.get("affected_run_ids"))
                evidence_refs = _as_string_list(raw.get("evidence_refs"))
                for duplicate in _duplicates(affected):
                    issues.append(
                        _obstruction(
                            "duplicate_affected_run",
                            f"{base}/affected_run_ids",
                            f"affected run {duplicate} occurs more than once",
                        )
                    )
                required_refs = {f"run:{item}" for item in affected}
                for missing in sorted(required_refs - set(evidence_refs)):
                    issues.append(
                        _obstruction(
                            "missing_incident_lineage",
                            f"{base}/evidence_refs",
                            f"required evidence reference {missing} is absent",
                        )
                    )

    fleet = sections.get("fleet_signal_evidence")
    if fleet is not None:
        summary = fleet.get("summary")
        signals = summary.get("signals") if isinstance(summary, Mapping) else []
        if isinstance(signals, Sequence) and not isinstance(
            signals, (str, bytes, bytearray)
        ):
            for index, raw in enumerate(signals):
                if not isinstance(raw, Mapping):
                    continue
                linkage = raw.get("linkage")
                if not isinstance(linkage, Mapping):
                    continue
                replay = linkage.get("replay")
                evidence_refs = _as_string_list(linkage.get("evidence_refs"))
                if isinstance(replay, Mapping) and replay.get("available") is True:
                    run_id = replay.get("run_id")
                    required = f"run:{run_id}" if isinstance(run_id, str) and run_id else None
                    if required and required not in evidence_refs:
                        issues.append(
                            _obstruction(
                                "missing_replay_lineage",
                                f"sections/fleet_signal_evidence/summary/signals/{index}/linkage/evidence_refs",
                                f"available replay requires evidence reference {required}",
                            )
                        )

    return EvidencePackAudit("certificate_validation", tuple(issues))


def compare_evidence_pack_audits(
    pack: Mapping[str, Any],
) -> EvidencePackAuditComparison:
    """Run ordinary and certificate audits on the same immutable candidate."""

    return EvidencePackAuditComparison(
        ordinary=audit_evidence_pack_ordinary(pack),
        certificate=audit_evidence_pack_certificate(pack),
    )


__all__ = [
    "EvidencePackAudit",
    "EvidencePackAuditComparison",
    "EvidencePackObstruction",
    "audit_evidence_pack_certificate",
    "audit_evidence_pack_ordinary",
    "compare_evidence_pack_audits",
]
