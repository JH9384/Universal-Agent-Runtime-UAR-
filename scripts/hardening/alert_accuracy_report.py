#!/usr/bin/env python3
"""Alert Accuracy Report — track fired / acted / ignored webhook alerts.

Usage:
    python scripts/hardening/alert_accuracy_report.py
        [--hours HOURS] [--output reports/alert_accuracy.md]

Generates a markdown report showing:
* Total alerts fired
* Action rate (acted upon)
* Ignore rate (no action taken)
* Unresolved rate (no response recorded)
* Average resolution time
* Breakdown by alert type
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def _get_tracker():
    """Get alert tracker bound to the default store."""
    from uar.api.alert_tracker import get_alert_tracker
    try:
        from uar.api.state import store
        return get_alert_tracker(store)
    except Exception:
        return get_alert_tracker()


def _generate_report(hours: int) -> str:
    tracker = _get_tracker()
    metrics = tracker.get_accuracy_metrics(hours=hours)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Alert Accuracy Report",
        "",
        f"**Generated:** {now}",
        f"**Window:** Last {hours} hours",
        "",
        "## Summary",
        "",
        f"- **Total fired:** {metrics['total_fired']}",
        f"- **Acted upon:** {metrics['acted']}",
        f"- **Ignored:** {metrics['ignored']}",
        f"- **Unresolved:** {metrics['unresolved']}",
        f"- **Action rate:** {metrics['action_rate']:.1%}",
        f"- **Ignore rate:** {metrics['ignore_rate']:.1%}",
        f"- **Unresolved rate:** {metrics['unresolved_rate']:.1%}",
    ]
    if metrics.get("avg_resolution_seconds") is not None:
        lines.append(
            f"- **Avg resolution time:** {metrics['avg_resolution_seconds']}s"
        )
    lines.append("")

    lines.append("## By Alert Type")
    lines.append("")
    if metrics.get("by_type"):
        lines.append("| Type | Fired | Acted | Ignored | Action Rate |")
        lines.append("|---|---|---|---|---|")
        for atype, counts in sorted(metrics["by_type"].items()):
            fired = counts.get("fired", 0)
            acted = counts.get("acted", 0)
            ignored = counts.get("ignored", 0)
            rate = acted / max(fired, 1)
            lines.append(
                f"| {atype} | {fired} | {acted} | {ignored} | {rate:.1%} |"
            )
    else:
        lines.append("*No alert type breakdown available*")
    lines.append("")

    lines.append("## Assessment")
    lines.append("")
    if metrics["total_fired"] == 0:
        lines.append("- No alerts fired in this window.")
    elif metrics["action_rate"] >= 0.7:
        lines.append("- **Action rate is high** — alerts are useful.")
    elif metrics["action_rate"] >= 0.3:
        lines.append(
            "- **Action rate is moderate** — some alerts may be noise."
        )
    else:
        lines.append(
            "- **Action rate is low** — alerts may be noise or not "
            "actionable."
        )

    if metrics["unresolved_rate"] > 0.3:
        lines.append(
            "- **Many unresolved alerts** — operators may be missing them."
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Alert Accuracy Report",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Time window in hours (default: 168 = 1 week)",
    )
    parser.add_argument(
        "--output",
        default="reports/alert_accuracy.md",
        help="Output markdown file",
    )
    args = parser.parse_args()

    report = _generate_report(args.hours)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
