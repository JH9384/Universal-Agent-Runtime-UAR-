"""Evidence Pack v2 composer.

Reuse-first evidence pack composition for D4C and later operator flows.

This module is intentionally thin: it composes existing section builders and
returns structured data plus markdown. It creates no new durable store and can
serve scripts, APIs, or report viewers as the canonical evidence-pack seam.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from uar.core.fleet_evidence_section import build_fleet_evidence_section
from uar.core.incident_evidence_section import build_incident_evidence_section
from uar.core.evidence_pack_correlation_section import (
    build_correlation_evidence_section,
)


def compose_evidence_pack_v2(
    records: Iterable[Dict[str, Any]],
    *,
    outcomes: Optional[List[Dict[str, Any]]] = None,
    recommendation_metadata: Optional[List[Dict[str, Any]]] = None,
    correlations: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[float] = None,
    title: str = "UAR Evidence Pack v2",
) -> Dict[str, Any]:
    """Compose an Evidence Pack v2 payload from reusable sections."""

    generated = time.time() if generated_at is None else generated_at
    record_list = list(records)
    outcome_rows = outcomes or []
    metadata_rows = recommendation_metadata or []
    fleet_section = build_fleet_evidence_section(
        record_list,
        outcomes=outcome_rows,
        recommendation_metadata=metadata_rows,
        generated_at=generated,
    )
    incident_section = build_incident_evidence_section(
        record_list,
        outcomes=outcome_rows,
        recommendation_metadata=metadata_rows,
        generated_at=generated,
    )
    correlation_section = build_correlation_evidence_section(
        correlations or [],
        generated_at=generated,
    )

    sections = [fleet_section, incident_section, correlation_section]
    markdown_parts = [
        f"# {title}",
        "",
        f"Generated at: `{generated}`",
        "",
    ]
    markdown_parts.extend(section["markdown"] for section in sections)

    return {
        "title": title,
        "version": "v2",
        "generated_at": generated,
        "sections": sections,
        "markdown": "\n\n".join(markdown_parts),
    }


__all__ = ["compose_evidence_pack_v2"]
