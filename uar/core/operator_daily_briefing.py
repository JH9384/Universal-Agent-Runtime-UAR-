"""Operator Daily Briefing composer.

D4C Phase 2 — Operator Daily Loop.

The briefing composes existing Mission Control, fleet summary, warnings,
trust summary, and evidence-pack data into a reusable operator opening view.
It creates no new store and no parallel operational truth.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from uar.core.evidence_pack_v2 import compose_evidence_pack_v2


def _priority_from_status(status: Optional[str]) -> str:
    if status == "critical":
        return "critical"
    if status == "warning":
        return "warning"
    return "nominal"


def build_operator_daily_briefing(
    mission_control: Dict[str, Any],
    *,
    evidence_pack: Optional[Dict[str, Any]] = None,
    generated_at: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a daily operator briefing from existing UAR payloads."""

    generated = time.time() if generated_at is None else generated_at
    fleet = mission_control.get("fleet_summary") or {}
    fleet_status = fleet.get("status") or "nominal"
    top_signal = fleet.get("top_signal")
    runtime = mission_control.get("runtime_health") or {}
    certification = mission_control.get("certification") or {}
    trust = mission_control.get("trust_summary") or {}
    warnings = mission_control.get("recent_warnings") or []

    priority = _priority_from_status(fleet_status)
    if runtime.get("tier") and str(runtime.get("tier")).lower() in {
        "critical",
        "failed",
        "unstable",
    }:
        priority = "critical"
    if certification.get("level") and str(
        certification.get("level")
    ).lower() in {
        "failed",
        "degraded",
    }:
        priority = "critical"

    next_actions: List[Dict[str, Any]] = []
    if top_signal:
        linkage = top_signal.get("linkage") or {}
        replay = linkage.get("replay") or {}
        next_actions.append(
            {
                "id": "inspect_top_fleet_signal",
                "label": "Inspect top fleet signal",
                "target": "health",
                "run_id": replay.get("run_id"),
                "available": True,
                "reason": top_signal.get("message"),
            }
        )
        if replay.get("available"):
            next_actions.append(
                {
                    "id": "open_replay",
                    "label": "Open replay for latest affected run",
                    "target": "replay",
                    "run_id": replay.get("run_id"),
                    "available": True,
                    "reason": (
                        "Replay context is available from fleet linkage."
                    ),
                }
            )
        recommendations = linkage.get("recommendations") or []
        if recommendations:
            next_actions.append(
                {
                    "id": "record_outcome",
                    "label": "Record recommendation outcome",
                    "target": "intelligence",
                    "recommendation_ids": recommendations,
                    "available": True,
                    "reason": "Fleet signal has linked recommendation IDs.",
                }
            )
    if evidence_pack:
        next_actions.append(
            {
                "id": "generate_evidence_pack",
                "label": "Review Evidence Pack v2",
                "target": "artifacts",
                "available": True,
                "reason": "Evidence Pack v2 is composed from current records.",
            }
        )

    if not next_actions:
        next_actions.append(
            {
                "id": "monitor",
                "label": "Monitor fleet health",
                "target": "health",
                "available": True,
                "reason": "No interrupting fleet signals detected.",
            }
        )

    summary = {
        "priority": priority,
        "fleet_status": fleet_status,
        "active_fleet_signals": fleet.get("active_signals", 0),
        "runtime_tier": runtime.get("tier"),
        "runtime_score": runtime.get("score"),
        "certification_level": certification.get("level"),
        "certification_score": certification.get("score"),
        "top_trusted": trust.get("top_trusted"),
        "top_trust_score": trust.get("top_trust_score"),
        "warning_count": len(warnings),
    }

    return {
        "generated_at": generated,
        "summary": summary,
        "top_signal": top_signal,
        "warnings": warnings[:10],
        "next_actions": next_actions,
        "evidence_pack": {
            "available": evidence_pack is not None,
            "section_count": len(evidence_pack.get("sections", []))
            if evidence_pack
            else 0,
            "markdown_preview": evidence_pack.get("markdown", "")[:2000]
            if evidence_pack
            else None,
        },
    }


def build_operator_daily_briefing_from_records(
    mission_control: Dict[str, Any],
    records: List[Dict[str, Any]],
    *,
    outcomes: Optional[List[Dict[str, Any]]] = None,
    recommendation_metadata: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[float] = None,
) -> Dict[str, Any]:
    """Build briefing and compose Evidence Pack v2 from supplied records."""

    generated = time.time() if generated_at is None else generated_at
    evidence_pack = compose_evidence_pack_v2(
        records,
        outcomes=outcomes or [],
        recommendation_metadata=recommendation_metadata or [],
        generated_at=generated,
    )
    return build_operator_daily_briefing(
        mission_control,
        evidence_pack=evidence_pack,
        generated_at=generated,
    )


__all__ = [
    "build_operator_daily_briefing",
    "build_operator_daily_briefing_from_records",
]
