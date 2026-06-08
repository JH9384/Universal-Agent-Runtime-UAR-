"""Fleet signal adapter for existing UAR alert surfaces.

D4C-S1.3 — Top Fleet Alert Routing.

This module converts the reuse-first ``fleet_summary`` shape into the same
alert dictionaries already consumed by ``/api/uar/alerts/summary`` and the
existing AlertBanner UI.  It creates no new endpoint, no new store, and no
parallel alert concept.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


_PRIORITY = {"critical": 0, "warning": 1, "info": 2}


def fleet_alert_from_summary(
    fleet_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Convert a Mission Control fleet summary into one alert candidate.

    The returned object intentionally follows the existing alert-summary
    dictionary shape: ``level``, ``source``, ``message``, and ``tab``.  Extra
    fields are included for existing/reused click-through behavior such as
    replay opening when ``run_id`` is present.
    """

    if not fleet_summary:
        return None
    top_signal = fleet_summary.get("top_signal")
    if not isinstance(top_signal, dict):
        return None

    level = str(top_signal.get("level") or "info").lower()
    if level not in _PRIORITY:
        level = "info"
    if level == "info":
        return None

    title = top_signal.get("title") or "Fleet signal"
    detail = top_signal.get("message") or "Fleet signal requires review"
    run_id = top_signal.get("latest_run_id")

    alert = {
        "level": level,
        "source": "fleet",
        "message": f"{title}: {detail}",
        "detail": top_signal,
        "tab": "health",
        "run_id": run_id,
        "scope": top_signal.get("scope"),
        "signal_id": top_signal.get("id"),
    }
    return alert


def merge_alerts_with_fleet(
    alerts: Iterable[Dict[str, Any]],
    fleet_summary: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return existing alerts plus a fleet alert candidate, priority sorted."""

    merged = list(alerts)
    fleet_alert = fleet_alert_from_summary(fleet_summary)
    if fleet_alert is not None:
        merged.append(fleet_alert)
    merged.sort(key=lambda a: _PRIORITY.get(str(a.get("level")), 2))
    return merged


__all__ = ["fleet_alert_from_summary", "merge_alerts_with_fleet"]
