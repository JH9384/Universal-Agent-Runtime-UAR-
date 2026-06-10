"""Evidence Pack v2 read-only builder.

D5E guardrail: this module must not mutate runtime state.
It assembles existing operational evidence into an explicit availability
contract for operator review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EvidenceSection:
    """A single Evidence Pack v2 section with explicit availability."""

    available: bool
    source: str
    data: Optional[Mapping[str, Any]] = None
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "source": self.source,
            "data": dict(self.data) if self.data is not None else None,
            "missing": list(self.missing),
        }


@dataclass(frozen=True)
class EvidencePack:
    """Read-only Evidence Pack v2 object."""

    evidence_pack_id: str
    generated_at: str
    authority_tag: str
    run_id: str
    signal: EvidenceSection
    mission_control: EvidenceSection
    replay: EvidenceSection
    burnin: EvidenceSection
    certification: EvidenceSection
    trust: EvidenceSection
    outcome: EvidenceSection
    closure: EvidenceSection

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_pack_id": self.evidence_pack_id,
            "generated_at": self.generated_at,
            "authority_tag": self.authority_tag,
            "run_id": self.run_id,
            "signal": self.signal.to_dict(),
            "mission_control": self.mission_control.to_dict(),
            "replay": self.replay.to_dict(),
            "burnin": self.burnin.to_dict(),
            "certification": self.certification.to_dict(),
            "trust": self.trust.to_dict(),
            "outcome": self.outcome.to_dict(),
            "closure": self.closure.to_dict(),
        }


def available_section(source: str, data: Mapping[str, Any]) -> EvidenceSection:
    """Create an available evidence section."""

    return EvidenceSection(
        available=True,
        source=source,
        data=dict(data),
        missing=[],
    )


def unavailable_section(source: str, reason: str) -> EvidenceSection:
    """Create an unavailable evidence section with explicit reason."""

    return EvidenceSection(
        available=False,
        source=source,
        data=None,
        missing=[reason],
    )


def build_evidence_pack(
    *,
    run_id: str,
    mission_control: Optional[Mapping[str, Any]] = None,
    replay: Optional[Mapping[str, Any]] = None,
    burnin: Optional[Mapping[str, Any]] = None,
    certification: Optional[Mapping[str, Any]] = None,
    trust: Optional[Mapping[str, Any]] = None,
    signal: Optional[Mapping[str, Any]] = None,
    outcome: Optional[Mapping[str, Any]] = None,
    closure: Optional[Mapping[str, Any]] = None,
    authority_tag: str = "v1.2.18-d5d-evidence-pack-field-map",
) -> EvidencePack:
    """Build a read-only Evidence Pack v2 from already-fetched data.

    The builder intentionally accepts source data as arguments. Fetching from
    stores, routers, or APIs belongs in later adapter layers so the core stays
    deterministic and testable.
    """

    if not run_id:
        raise ValueError("run_id is required")

    pack_id = f"evidence-pack:{run_id}"

    return EvidencePack(
        evidence_pack_id=pack_id,
        generated_at=_utc_now_iso(),
        authority_tag=authority_tag,
        run_id=run_id,
        signal=(
            available_section("signal", signal)
            if signal is not None
            else unavailable_section("signal", "signal data not provided")
        ),
        mission_control=(
            available_section("mission_control", mission_control)
            if mission_control is not None
            else unavailable_section(
                "mission_control", "mission control snapshot not provided"
            )
        ),
        replay=(
            available_section("replay", replay)
            if replay is not None
            else unavailable_section("replay", "replay evidence not provided")
        ),
        burnin=(
            available_section("burnin", burnin)
            if burnin is not None
            else unavailable_section("burnin", "burn-in evidence not provided")
        ),
        certification=(
            available_section("certification", certification)
            if certification is not None
            else unavailable_section(
                "certification", "certification evidence not provided"
            )
        ),
        trust=(
            available_section("trust", trust)
            if trust is not None
            else unavailable_section("trust", "trust evidence not provided")
        ),
        outcome=(
            available_section("outcome", outcome)
            if outcome is not None
            else unavailable_section("outcome", "operator outcome not provided")
        ),
        closure=(
            available_section("closure", closure)
            if closure is not None
            else unavailable_section("closure", "closure state not provided")
        ),
    )


def render_evidence_pack_markdown(pack: EvidencePack) -> str:
    """Render a compact markdown Evidence Pack v2 summary."""

    data = pack.to_dict()
    lines = [
        f"# Evidence Pack v2 — {pack.run_id}",
        "",
        "## Canonical Operator Path",
        "",
        "```text",
        "Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement",
        "```",
        "",
        "## Metadata",
        "",
        f"- Evidence pack ID: `{pack.evidence_pack_id}`",
        f"- Generated at: `{pack.generated_at}`",
        f"- Authority tag: `{pack.authority_tag}`",
        f"- Run ID: `{pack.run_id}`",
        "",
        "## Section Availability",
        "",
        "| Section | Available | Source | Missing |",
        "| --- | --- | --- | --- |",
    ]

    for key in (
        "signal",
        "mission_control",
        "replay",
        "burnin",
        "certification",
        "trust",
        "outcome",
        "closure",
    ):
        section = data[key]
        missing = ", ".join(section["missing"]) if section["missing"] else "-"
        lines.append(
            f"| `{key}` | `{section['available']}` | `{section['source']}` | {missing} |"
        )

    lines.append("")
    return "\n".join(lines)


__all__ = [
    "EvidencePack",
    "EvidenceSection",
    "available_section",
    "build_evidence_pack",
    "render_evidence_pack_markdown",
    "unavailable_section",
]
