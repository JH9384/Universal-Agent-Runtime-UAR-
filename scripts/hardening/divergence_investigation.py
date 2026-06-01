#!/usr/bin/env python3
"""Divergence Investigation Queue — Ω-7B.1.

Captures recommendations where confidence and trust strongly disagree.
These outliers are investigation candidates for heuristic or operational
reality flaws.

Usage:
    python scripts/hardening/divergence_investigation.py \
        [--api-url URL] [--api-key KEY] [--output FILE]

Writes a JSON file with two queues:
- high_confidence_low_trust:   confidence > 0.90, trust < 0.40
- low_confidence_high_trust:    confidence < 0.50, trust > 0.80
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

import requests


def fetch(endpoint: str, api_url: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}{endpoint}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def classify_divergence(rec: dict) -> str | None:
    """Return divergence type or None if not divergent."""
    conf = rec.get("confidence", 0.0)
    trust = rec.get("trust_score", 0.0)
    if conf > 0.90 and trust < 0.40:
        return "high_confidence_low_trust"
    if conf < 0.50 and trust > 0.80:
        return "low_confidence_high_trust"
    return None


def build_divergence_report(
    recommendations: List[dict],
) -> dict:
    queues = {
        "high_confidence_low_trust": [],
        "low_confidence_high_trust": [],
    }
    for rec in recommendations:
        div_type = classify_divergence(rec)
        if div_type is None:
            continue
        queues[div_type].append(
            {
                "recommendation_id": rec.get("recommendation_id"),
                "title": rec.get("title", ""),
                "category": rec.get("category", ""),
                "source": rec.get("source", ""),
                "confidence": rec.get("confidence"),
                "trust_score": rec.get("trust_score"),
                "base_confidence": rec.get("base_confidence"),
                "adaptive_modifier": rec.get("adaptive_modifier"),
                "drift_penalty": rec.get("drift_penalty"),
                "affected_runs": rec.get("affected_runs", []),
            }
        )

    # Sort by severity (largest gap first)
    for key in queues:
        if key == "high_confidence_low_trust":
            queues[key].sort(
                key=lambda r: r["confidence"] - r["trust_score"],
                reverse=True,
            )
        else:
            queues[key].sort(
                key=lambda r: r["trust_score"] - r["confidence"],
                reverse=True,
            )

    return {
        "total_divergences": sum(len(v) for v in queues.values()),
        "queues": queues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ω-7B.1 Divergence Investigation Queue",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="UAR API base URL",
    )
    parser.add_argument(
        "--api-key",
        default="dev-key-12345",
        help="API key for authentication",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    try:
        recs_data = fetch(
            "/api/uar/recommendations",
            args.api_url,
            args.api_key,
        )
    except requests.RequestException as e:
        print(f"API request failed: {e}", file=sys.stderr)
        return 1

    report = build_divergence_report(
        recs_data.get("recommendations", [])
    )
    report["meta"] = {
        "api_url": args.api_url,
        "recommendation_count": len(recs_data.get("recommendations", [])),
        "trust_ranking_enabled": recs_data.get(
            "trust_ranking_enabled", False
        ),
    }
    payload = json.dumps(report, indent=2)

    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload + "\n")
        print(f"Divergence report written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
