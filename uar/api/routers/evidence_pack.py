"""Read-only Evidence Pack v2 API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from uar.core.evidence_pack import build_evidence_pack, render_evidence_pack_markdown

router = APIRouter(prefix="/api/uar/evidence-pack", tags=["evidence-pack"])


def _validate_run_id(run_id: str) -> str:
    normalized = run_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="run_id must not be empty")
    return normalized


@router.get("/{run_id}")
def get_evidence_pack(
    run_id: str,
    include_markdown: bool = Query(default=False),
    include_unavailable: bool = Query(default=True),
    signal_id: str | None = Query(default=None),
    recommendation_id: str | None = Query(default=None),
    outcome_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return a read-only Evidence Pack v2 object.

    This endpoint intentionally assembles a pack from the core D5E builder
    without mutating runtime state or writing artifacts.
    """

    normalized_run_id = _validate_run_id(run_id)

    signal = {"signal_id": signal_id} if signal_id else None
    outcome = {"outcome_id": outcome_id} if outcome_id else None
    trust = {"recommendation_id": recommendation_id} if recommendation_id else None

    pack = build_evidence_pack(
        run_id=normalized_run_id,
        authority_tag="v1.2.36-d5q-evidence-pack-api-contract",
        signal=signal,
        trust=trust,
        outcome=outcome,
    )

    pack_data = pack.to_dict()

    if not include_unavailable:
        pack_data = {
            key: value
            for key, value in pack_data.items()
            if not isinstance(value, dict) or value.get("available", True)
        }

    return {
        "status": "ok",
        "run_id": normalized_run_id,
        "evidence_pack": pack_data,
        "markdown": render_evidence_pack_markdown(pack) if include_markdown else None,
    }


__all__ = ["router"]
