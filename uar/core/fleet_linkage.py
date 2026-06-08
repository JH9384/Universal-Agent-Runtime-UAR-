"""Replay, incident, and recommendation linkage for fleet signals.

D4C-S1.4 — Replay and Incident Linkage.

This module does not create a fleet-specific incident system.  It translates
existing FleetSignal dictionaries into reusable link context for current and
future operator surfaces.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_fleet_signal_linkage(
    signal: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build reusable navigation context from a fleet signal dict.

    The returned shape is intentionally UI/API neutral.  Current UI can use
    ``replay.run_id`` immediately; incident and recommendation sections remain
    existing IDs rather than a new fleet-specific workbench.
    """

    if not isinstance(signal, dict):
        return {
            "has_signal": False,
            "replay": None,
            "incidents": [],
            "recommendations": [],
            "evidence_refs": [],
        }

    run_id = signal.get("latest_run_id")
    incidents = signal.get("linked_incident_ids") or []
    recommendations = signal.get("linked_recommendation_ids") or []
    evidence_refs = signal.get("evidence_refs") or []

    return {
        "has_signal": True,
        "signal_id": signal.get("id"),
        "scope": signal.get("scope"),
        "level": signal.get("level"),
        "replay": {
            "run_id": run_id,
            "available": bool(run_id),
        },
        "incidents": [str(v) for v in incidents if v],
        "recommendations": [str(v) for v in recommendations if v],
        "evidence_refs": [str(v) for v in evidence_refs if v],
    }


def attach_linkage_to_fleet_summary(
    fleet_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Attach link context to top and listed fleet signals.

    This returns a shallow copy and does not mutate the input summary.
    """

    if not isinstance(fleet_summary, dict):
        return fleet_summary

    result = dict(fleet_summary)
    top_signal = result.get("top_signal")
    if isinstance(top_signal, dict):
        top_copy = dict(top_signal)
        top_copy["linkage"] = build_fleet_signal_linkage(top_copy)
        result["top_signal"] = top_copy

    signals = []
    for signal in result.get("signals") or []:
        if isinstance(signal, dict):
            sig_copy = dict(signal)
            sig_copy["linkage"] = build_fleet_signal_linkage(sig_copy)
            signals.append(sig_copy)
    result["signals"] = signals
    return result


__all__ = ["build_fleet_signal_linkage", "attach_linkage_to_fleet_summary"]
