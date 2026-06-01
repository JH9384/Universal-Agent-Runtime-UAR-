#!/usr/bin/env python3
"""Ω-7B.1 Operational Validation — Trust metrics collection script.

Usage:
    python scripts/hardening/trust_validation.py
        [--api-url URL] [--api-key KEY]

Outputs a JSON report with the four Ω-7B.1 burn-in metrics:
1. Trust Distribution
2. Ranking Delta
3. Outcome Correlation
4. Drift Discovery
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

import requests


def fetch(endpoint: str, api_url: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}{endpoint}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def compute_trust_distribution(trust_types: List[dict]) -> dict:
    """Bucket trust scores into operator-facing bands."""
    bands = {
        "highly_trusted": 0,
        "trusted": 0,
        "watch": 0,
        "weak": 0,
        "untrusted": 0,
    }
    for t in trust_types:
        score = t.get("trust_score", 0.0)
        if score >= 0.80:
            bands["highly_trusted"] += 1
        elif score >= 0.60:
            bands["trusted"] += 1
        elif score >= 0.40:
            bands["watch"] += 1
        elif score >= 0.20:
            bands["weak"] += 1
        else:
            bands["untrusted"] += 1
    return bands


def compute_ranking_deltas(
    recommendations: List[dict],
) -> List[dict]:
    """Find recommendations where confidence rank diverges from trust rank."""
    # Sort by confidence descending to get confidence rank
    by_conf = sorted(
        recommendations,
        key=lambda r: r.get("confidence", 0.0),
        reverse=True,
    )
    conf_ranks = {
        r["recommendation_id"]: i + 1 for i, r in enumerate(by_conf)
    }

    # Sort by trust_score descending to get trust rank
    by_trust = sorted(
        recommendations,
        key=lambda r: r.get("trust_score", 0.0),
        reverse=True,
    )
    trust_ranks = {
        r["recommendation_id"]: i + 1 for i, r in enumerate(by_trust)
    }

    deltas = []
    for rec in recommendations:
        rid = rec["recommendation_id"]
        c_rank = conf_ranks.get(rid)
        t_rank = trust_ranks.get(rid)
        if c_rank is None or t_rank is None:
            continue
        delta = abs(c_rank - t_rank)
        if delta >= 2:  # Only report meaningful divergences
            deltas.append(
                {
                    "recommendation_id": rid,
                    "title": rec.get("title", ""),
                    "confidence_rank": c_rank,
                    "trust_rank": t_rank,
                    "delta": delta,
                    "confidence": rec.get("confidence"),
                    "trust_score": rec.get("trust_score"),
                }
            )

    deltas.sort(key=lambda x: -x["delta"])
    return deltas


def compute_outcome_correlation(
    trust_types: List[dict],
    effectiveness_types: List[dict],
) -> dict:
    """Compute Spearman-like rank correlation between trust and resolution."""
    try:
        from scipy.stats import spearmanr  # type: ignore[import-untyped]
    except ImportError:
        return {
            "available": False,
            "note": "Install scipy for correlation: pip install scipy",
        }

    # Build lookup: type -> resolution_rate
    eff_map = {
        t["type"]: t.get("resolution_rate", 0.0)
        for t in effectiveness_types
        if "type" in t
    }

    trust_scores = []
    resolution_rates = []
    for t in trust_types:
        type_name = t.get("type", "")
        if type_name in eff_map:
            trust_scores.append(t.get("trust_score", 0.0))
            resolution_rates.append(eff_map[type_name])

    if len(trust_scores) < 3:
        return {
            "available": True,
            "correlation": None,
            "p_value": None,
            "sample_size": len(trust_scores),
            "note": (
                "Insufficient data "
                "(need 3+ types with both trust and outcomes)"
            ),
        }

    corr, pval = spearmanr(trust_scores, resolution_rates)
    return {
        "available": True,
        "correlation": round(float(corr), 3) if corr is not None else None,
        "p_value": round(float(pval), 4) if pval is not None else None,
        "sample_size": len(trust_scores),
        "assessment": (
            "good" if corr is not None and corr >= 0.5 else
            "acceptable" if corr is not None and corr >= 0.3 else
            "poor" if corr is not None and corr >= 0.0 else
            "negative"
        ),
    }


def find_drift_signals(
    trust_types: List[dict],
) -> List[dict]:
    """Find high-confidence + high-trust types with negative drift."""
    signals = []
    for t in trust_types:
        trust = t.get("trust_score", 0.0)
        drift_penalty = t.get("drift_penalty", 0.0)
        eff = t.get("effectiveness_component", 0.0)
        if trust >= 0.60 and drift_penalty > 0.0:
            signals.append(
                {
                    "type": t.get("type", ""),
                    "trust_score": trust,
                    "effectiveness": eff,
                    "drift_penalty": drift_penalty,
                    "severity": (
                        "critical" if drift_penalty > 0.20 else "warning"
                    ),
                    "note": (
                        "Historically trusted but recent outcomes degraded"
                    ),
                }
            )
    signals.sort(key=lambda x: (-x["drift_penalty"], -x["trust_score"]))
    return signals


def build_report(
    trust_data: dict,
    recs_data: dict,
    eff_data: dict,
) -> dict:
    trust_types = trust_data.get("recommendation_types", [])
    recommendations = recs_data.get("recommendations", [])
    eff_types = eff_data.get("recommendation_types", [])

    return {
        "generated_at": trust_data.get("generated_at"),
        "system_calibration_error": trust_data.get(
            "system_calibration_error"
        ),
        "metrics": {
            "trust_distribution": compute_trust_distribution(trust_types),
            "ranking_deltas": compute_ranking_deltas(recommendations),
            "outcome_correlation": compute_outcome_correlation(
                trust_types, eff_types
            ),
            "drift_signals": find_drift_signals(trust_types),
        },
        "raw_counts": {
            "trust_types": len(trust_types),
            "recommendations": len(recommendations),
            "effectiveness_types": len(eff_types),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ω-7B.1 Trust Operational Validation",
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
        trust_data = fetch(
            "/api/uar/recommendations/trust",
            args.api_url,
            args.api_key,
        )
        recs_data = fetch(
            "/api/uar/recommendations",
            args.api_url,
            args.api_key,
        )
        eff_data = fetch(
            "/api/uar/recommendations/effectiveness",
            args.api_url,
            args.api_key,
        )
    except requests.RequestException as e:
        print(f"API request failed: {e}", file=sys.stderr)
        return 1

    report = build_report(trust_data, recs_data, eff_data)
    payload = json.dumps(report, indent=2)

    if args.output == "-":
        print(payload)
    else:
        import pathlib

        pathlib.Path(args.output).write_text(payload + "\n")
        print(f"Report written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
