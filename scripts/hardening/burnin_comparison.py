#!/usr/bin/env python3
"""Burn-In Comparison Engine — compare 24h/72h/168h runs automatically.

Usage:
    python scripts/hardening/burnin_comparison.py
        [--api-url URL] [--api-key KEY]
        [--output reports/burnin_comparison.md]

Questions answered:
* Did memory grow?
* Did trust drift?
* Did latency increase?
* Did replay volume change?
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def _fetch(endpoint: str, api_url: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}{endpoint}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def _extract_burnin_metrics(report: dict) -> Dict[str, Any]:
    """Extract comparable metrics from a burn-in report dict."""
    evidence = report.get("evidence", [])
    metrics = {
        "timestamp": report.get("timestamp", 0),
        "score": report.get("score", 0),
        "passed": report.get("passed", False),
        "error_count": len(report.get("errors", [])),
        "evidence_count": len(evidence),
    }
    # Sum scores from evidence categories if available
    for e in evidence:
        scenario = e.get("scenario", "").lower()
        score = e.get("score", 0)
        if "memory" in scenario:
            metrics["memory_score"] = score
        elif "latency" in scenario or "websocket" in scenario:
            metrics["latency_score"] = score
        elif "replay" in scenario:
            metrics["replay_score"] = score
        elif "trust" in scenario:
            metrics["trust_score"] = score
    return metrics


def _format_report(report: dict) -> str:
    m = _extract_burnin_metrics(report)
    ts = datetime.fromtimestamp(
        m["timestamp"], tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"- **Date:** {ts}",
        f"- **Score:** {m['score']}/100",
        f"- **Passed:** {'Yes' if m['passed'] else 'No'}",
        f"- **Errors:** {m['error_count']}",
        f"- **Evidence items:** {m['evidence_count']}",
    ]
    for key in (
        "memory_score", "latency_score", "replay_score", "trust_score",
    ):
        if key in m:
            lines.append(
                f"- **{key.replace('_', ' ').title()}:** {m[key]}"
            )
    return "\n".join(lines) + "\n"


def _trend_direction(
    current: Optional[float],
    previous: Optional[float],
    lower_is_better: bool = False,
) -> str:
    if current is None or previous is None:
        return "?"
    if current == previous:
        return "→"
    if lower_is_better:
        return "↓" if current < previous else "↑"
    return "↑" if current > previous else "↓"


def _compare_reports(reports: List[dict]) -> str:
    if len(reports) < 2:
        return "*Need at least 2 reports to compare*\n"

    # Sort by timestamp ascending
    reports = sorted(reports, key=lambda r: r.get("timestamp", 0))
    first = _extract_burnin_metrics(reports[0])
    latest = _extract_burnin_metrics(reports[-1])

    # Also compute averages over last 24h, 72h, 168h windows
    now = latest["timestamp"]
    windows = {
        "24h": now - 86400,
        "72h": now - 259200,
        "168h": now - 604800,
    }
    window_avgs: Dict[str, Dict[str, Any]] = {}
    for label, cutoff in windows.items():
        window_reports = [
            r for r in reports
            if r.get("timestamp", 0) >= cutoff
        ]
        if window_reports:
            scores = [
                _extract_burnin_metrics(r)["score"]
                for r in window_reports
            ]
            window_avgs[label] = {
                "count": len(window_reports),
                "avg_score": round(sum(scores) / len(scores), 1),
                "pass_rate": round(
                    sum(
                        1 for r in window_reports
                        if r.get("passed", False)
                    ) / len(window_reports),
                    2,
                ),
            }

    lines = []
    lines.append("## Comparison Summary")
    lines.append("")
    lines.append("| Metric | First | Latest | Trend |")
    lines.append("|---|---|---|---|")

    score_trend = _trend_direction(latest["score"], first["score"])
    lines.append(
        f"| Score | {first['score']} | {latest['score']} | {score_trend} |"
    )

    err_trend = _trend_direction(
        latest["error_count"], first["error_count"],
        lower_is_better=True,
    )
    lines.append(
        f"| Errors | {first['error_count']} | {latest['error_count']} | "
        f"{err_trend} |"
    )

    ev_trend = _trend_direction(
        latest["evidence_count"], first["evidence_count"],
    )
    lines.append(
        f"| Evidence | {first['evidence_count']} | "
        f"{latest['evidence_count']} | {ev_trend} |"
    )

    for key in (
        "memory_score", "latency_score", "replay_score", "trust_score",
    ):
        if key in first or key in latest:
            f_val = first.get(key, "N/A")
            l_val = latest.get(key, "N/A")
            if isinstance(f_val, (int, float)) and isinstance(
                l_val, (int, float)
            ):
                t = _trend_direction(l_val, f_val)
            else:
                t = "?"
            lines.append(
                f"| {key.replace('_', ' ').title()} | {f_val} | "
                f"{l_val} | {t} |"
            )

    lines.append("")
    lines.append("## Window Averages")
    lines.append("")
    lines.append("| Window | Reports | Avg Score | Pass Rate |")
    lines.append("|---|---|---|---|")
    for label in ("24h", "72h", "168h"):
        if label in window_avgs:
            w = window_avgs[label]
            lines.append(
                f"| {label} | {w['count']} | {w['avg_score']} | "
                f"{w['pass_rate']:.0%} |"
            )
        else:
            lines.append(f"| {label} | — | — | — |")
    lines.append("")

    # Trend narrative
    lines.append("## Trend Narrative")
    lines.append("")
    if latest["score"] < first["score"]:
        lines.append(
            f"- Score declined from {first['score']} to {latest['score']}."
        )
    elif latest["score"] > first["score"]:
        lines.append(
            f"- Score improved from {first['score']} to {latest['score']}."
        )
    else:
        lines.append(f"- Score stable at {latest['score']}.")

    if latest["error_count"] > first["error_count"]:
        lines.append("- Errors increased.")
    elif latest["error_count"] < first["error_count"]:
        lines.append("- Errors decreased.")
    else:
        lines.append("- Error count unchanged.")

    if not window_avgs:
        lines.append("- No window data available for trend analysis.")
    else:
        # Check if pass rate is declining in recent windows
        for label in ("24h", "72h", "168h"):
            if label in window_avgs:
                pr = window_avgs[label]["pass_rate"]
                if pr < 1.0:
                    lines.append(
                        f"- {label} pass rate is {pr:.0%} — not all green."
                    )
                break

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Burn-In Comparison Engine",
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="dev-key-12345")
    parser.add_argument(
        "--output",
        default="reports/burnin_comparison.md",
        help="Output markdown file",
    )
    args = parser.parse_args()

    try:
        # Try the history endpoint first, fall back to latest
        data = _fetch(
            "/api/uar/burnin/reports?limit=50",
            args.api_url, args.api_key,
        )
        reports = data.get("reports", [])
        if not reports:
            # Fallback to single latest report
            latest = _fetch(
                "/api/uar/burnin/latest", args.api_url, args.api_key
            )
            reports = [latest]
    except requests.RequestException as e:
        print(f"API request failed: {e}", file=sys.stderr)
        return 1

    if not reports:
        print("No burn-in reports found.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Burn-In Comparison Report",
        "",
        f"**Generated:** {now}",
        f"**Reports analyzed:** {len(reports)}",
        "",
    ]

    # Latest report detail
    latest = max(reports, key=lambda r: r.get("timestamp", 0))
    lines.append("## Latest Report")
    lines.append("")
    lines.append(_format_report(latest))

    # Comparison
    lines.append(_compare_reports(reports))

    # Full history table
    lines.append("## Full History")
    lines.append("")
    lines.append("| # | Date | Score | Passed | Errors |")
    lines.append("|---|---|---|---|---|")
    sorted_reports = sorted(reports, key=lambda x: x.get("timestamp", 0))
    for i, r in enumerate(sorted_reports):
        m = _extract_burnin_metrics(r)
        ts = datetime.fromtimestamp(
            m["timestamp"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M")
        passed = "Yes" if m["passed"] else "No"
        lines.append(
            f"| {i + 1} | {ts} | {m['score']} | "
            f"{passed} | {m['error_count']} |"
        )
    lines.append("")

    report = "\n".join(lines)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
