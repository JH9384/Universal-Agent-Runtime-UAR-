"""Timeline projection from RuntimeEvent traces.

Converts a validated event stream into a chronological summary
suitable for UI rendering and burn-in certification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from uar.core.contracts import RunRecord


def project_timeline(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Project a RuntimeEvent trace onto a timeline.

    Returns:
        dict with keys: phases, skills, total_duration_sec,
        event_types, errors, summary.
    """
    if not events:
        return {
            "phases": [],
            "skills": [],
            "total_duration_sec": 0.0,
            "event_types": [],
            "errors": [],
            "summary": {"status": "unknown", "skill_count": 0},
        }

    start_ts = events[0].get("timestamp", 0.0)
    end_ts = events[-1].get("timestamp", start_ts)

    phases: List[Dict[str, Any]] = []
    skills: List[Dict[str, Any]] = []
    errors: List[str] = []
    event_types: List[str] = []
    current_skill: Optional[str] = None
    skill_start_ts: float = start_ts

    for ev in events:
        etype = ev.get("type", "unknown")
        event_types.append(etype)
        ts = ev.get("timestamp", start_ts)

        if etype == "skill_start" and ev.get("skill"):
            current_skill = ev["skill"]
            skill_start_ts = ts
            phases.append({
                "type": "skill",
                "name": current_skill,
                "start_ts": ts,
            })
        elif etype == "skill_complete" and current_skill:
            duration = max(0.0, ts - skill_start_ts)
            skills.append({
                "name": current_skill,
                "duration_sec": round(duration, 3),
                "status": "completed",
            })
            current_skill = None
        elif etype == "skill_failed" and ev.get("skill"):
            duration = max(0.0, ts - skill_start_ts)
            skills.append({
                "name": ev["skill"],
                "duration_sec": round(duration, 3),
                "status": "failed",
            })
            current_skill = None
        elif etype == "recipe_start":
            rid = ev.get("payload", {}).get("recipe_id", "unknown")
            phases.append({"type": "recipe", "name": rid, "start_ts": ts})
        elif etype == "recipe_end":
            rid = ev.get("payload", {}).get("recipe_id", "unknown")
            phases.append({"type": "recipe_end", "name": rid, "end_ts": ts})
        elif etype == "error" and ev.get("error"):
            errors.append(ev["error"])

    # Compute status from terminal event
    status = "unknown"
    final_payload = events[-1].get("payload", {})
    if isinstance(final_payload, dict):
        status = final_payload.get("status", status)

    return {
        "phases": phases,
        "skills": skills,
        "total_duration_sec": round(max(0.0, end_ts - start_ts), 3),
        "event_types": event_types,
        "errors": errors,
        "summary": {
            "status": status,
            "skill_count": len(skills),
            "error_count": len(errors),
        },
    }


def timeline_from_record(record: RunRecord) -> Dict[str, Any]:
    """Convenience: project timeline from a RunRecord."""
    return project_timeline(record.events)
