#!/usr/bin/env python3
"""Certification Package — Track 4.

Single export of system state + metrics for operational validation.
Produces a timestamped JSON bundle containing:
- Mission Control snapshot
- Trust scores
- Effectiveness rankings
- Calibration data
- Recommendation metadata
- Outcome counts
- Burn-in status

Usage:
    python scripts/hardening/certification_package.py \
        --api-url http://localhost:8000 \
        --output reports/certification/cert_YYYYMMDD.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests


class CertificationCollector:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def _get(self, endpoint: str, timeout: int = 30) -> dict:
        url = f"{self.api_url}{endpoint}"
        response = requests.get(url, headers=self.headers, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def collect(self) -> Dict[str, Any]:
        """Gather all certification-relevant data."""
        package = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "api_url": self.api_url,
            "sections": {},
        }

        # Mission Control
        try:
            mc = self._get("/api/uar/mission-control")
            package["sections"]["mission_control"] = {
                "timestamp": mc.get("timestamp"),
                "active_runs": mc.get("active_runs"),
                "trust_summary": mc.get("trust_summary"),
                "recent_warnings_count": len(mc.get("recent_warnings", [])),
            }
        except requests.RequestException as e:
            package["sections"]["mission_control"] = {"error": str(e)}

        # Trust
        try:
            trust = self._get("/api/uar/recommendations/trust")
            package["sections"]["trust"] = {
                "generated_at": trust.get("generated_at"),
                "system_calibration_error": trust.get(
                    "system_calibration_error"
                ),
                "type_count": len(
                    trust.get("recommendation_types", [])
                ),
                "top_trusted": (
                    trust.get("recommendation_types", [])[0]
                    if trust.get("recommendation_types")
                    else None
                ),
            }
        except requests.RequestException as e:
            package["sections"]["trust"] = {"error": str(e)}

        # Effectiveness
        try:
            eff = self._get("/api/uar/recommendations/effectiveness")
            package["sections"]["effectiveness"] = {
                "generated_at": eff.get("generated_at"),
                "type_count": len(
                    eff.get("recommendation_types", [])
                ),
            }
        except requests.RequestException as e:
            package["sections"]["effectiveness"] = {"error": str(e)}

        # Calibration
        try:
            cal = self._get("/api/uar/recommendations/calibration")
            package["sections"]["calibration"] = {
                "generated_at": cal.get("generated_at"),
                "overall_calibration_error": cal.get(
                    "overall_calibration_error"
                ),
            }
        except requests.RequestException as e:
            package["sections"]["calibration"] = {"error": str(e)}

        # Recommendations
        try:
            recs = self._get(
                "/api/uar/recommendations?hours=24&limit=1000"
            )
            package["sections"]["recommendations"] = {
                "count": len(recs.get("recommendations", [])),
                "trust_ranking_enabled": recs.get(
                    "trust_ranking_enabled", False
                ),
                "divergence_count": sum(
                    1
                    for r in recs.get("recommendations", [])
                    if (r.get("confidence", 0) > 0.90
                        and r.get("trust_score", 0) < 0.40)
                    or (r.get("confidence", 0) < 0.50
                        and r.get("trust_score", 0) > 0.80)
                ),
            }
        except requests.RequestException as e:
            package["sections"]["recommendations"] = {"error": str(e)}

        # Quality
        try:
            qual = self._get("/api/uar/recommendations/quality")
            package["sections"]["quality"] = {
                "generated_at": qual.get("generated_at"),
                "overall_resolution_rate": qual.get(
                    "overall_resolution_rate"
                ),
                "total_resolved": qual.get("total_resolved"),
                "total_recurred": qual.get("total_recurred"),
            }
        except requests.RequestException as e:
            package["sections"]["quality"] = {"error": str(e)}

        return package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Certification package export",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="UAR API base URL",
    )
    parser.add_argument(
        "--api-key",
        default="dev-key-12345",
        help="API key",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: auto-generated)",
    )
    args = parser.parse_args()

    collector = CertificationCollector(args.api_url, args.api_key)

    print("Collecting certification package…")
    package = collector.collect()

    report_dir = Path("reports/certification")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = args.output or str(
        report_dir / f"certification_{timestamp}.json"
    )

    Path(output_file).write_text(
        json.dumps(package, indent=2) + "\n"
    )
    print(f"Certification package: {output_file}")

    # Summary
    sections = package.get("sections", {})
    print("\nPackage Summary:")
    for name, data in sections.items():
        if "error" in data:
            print(f"  {name}: ERROR — {data['error']}")
        else:
            print(f"  {name}: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
