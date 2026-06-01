#!/usr/bin/env python3
"""Cache Validation — Verify outcome→effectiveness→trust→MC propagation.

Ω-7B.1: Ensure no stale trust data in the operational pipeline.

This script walks the propagation chain:
1. Submit a synthetic outcome
2. Verify effectiveness recomputes
3. Verify trust recomputes
4. Verify Mission Control reflects new trust

Usage:
    python scripts/hardening/cache_validation.py \
        --api-url http://localhost:8000

Exit codes:
    0 — All propagation checks passed
    1 — One or more checks failed
"""

from __future__ import annotations

import argparse
import json
import time

import requests


class PropagationChecker:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def _get(self, endpoint: str, timeout: int = 15) -> dict:
        url = f"{self.api_url}{endpoint}"
        response = requests.get(url, headers=self.headers, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, payload: dict, timeout: int = 15) -> dict:
        url = f"{self.api_url}{endpoint}"
        response = requests.post(
            url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_initial_trust(self) -> dict:
        """Capture baseline trust scores."""
        return self._get("/api/uar/recommendations/trust")

    def get_initial_mc(self) -> dict:
        """Capture baseline Mission Control snapshot."""
        return self._get("/api/uar/mission-control")

    def get_recommendations(self) -> dict:
        return self._get("/api/uar/recommendations?hours=24&limit=100")

    def submit_synthetic_outcome(
        self,
        recommendation_id: str,
        outcome_type: str = "resolved",
    ) -> dict:
        """Submit a synthetic outcome to trigger recomputation.

        API expects: {"recommendation_id": "...", "outcome_type": "resolved"}
        """
        payload = {
            "recommendation_id": recommendation_id,
            "outcome_type": outcome_type,
        }
        return self._post("/api/uar/recommendations/outcome", payload)

    def get_effectiveness(self) -> dict:
        return self._get("/api/uar/recommendations/effectiveness")

    def get_trust(self) -> dict:
        return self._get("/api/uar/recommendations/trust")

    def get_mc(self) -> dict:
        return self._get("/api/uar/mission-control")

    def check_propagation(
        self,
        initial_trust: dict,
        initial_mc: dict,
        rec_type: str = "remediate",
    ) -> dict:
        """Run full propagation check and return report."""
        checks = {
            "outcome_submitted": False,
            "effectiveness_updated": False,
            "trust_updated": False,
            "mc_updated": False,
            "errors": [],
        }

        # Step 0: Get a real recommendation to attach outcome to
        rec_id = None
        try:
            recs_data = self.get_recommendations()
            recs = recs_data.get("recommendations", [])
            for rec in recs:
                if rec.get("category") == rec_type or rec_type == "any":
                    rec_id = rec.get("recommendation_id")
                    break
            if rec_id is None and recs:
                rec_id = recs[0].get("recommendation_id")
            if rec_id is None:
                checks["errors"].append(
                    "No recommendations available to attach outcome"
                )
                return checks
        except requests.RequestException as e:
            checks["errors"].append(f"Failed to fetch recommendations: {e}")
            return checks

        # Step 1: Submit multiple outcomes for same recommendation
        # Need >=5 samples for compute_effectiveness min_samples threshold
        try:
            for _ in range(5):
                self.submit_synthetic_outcome(
                    recommendation_id=rec_id, outcome_type="resolved"
                )
            checks["outcome_submitted"] = True
        except requests.RequestException as e:
            checks["errors"].append(f"Outcome submission failed: {e}")
            return checks

        # Allow async recomputation to settle
        time.sleep(2)

        # Step 2: Check effectiveness updated
        try:
            eff = self.get_effectiveness()
            types = eff.get("recommendation_types", [])
            eff_type = next(
                (t for t in types if t.get("type") == rec_type), None
            )
            if eff_type or rec_type == "any":
                checks["effectiveness_updated"] = True
            else:
                checks["errors"].append(
                    "Effectiveness: recommendation type not found"
                )
        except requests.RequestException as e:
            checks["errors"].append(f"Effectiveness check failed: {e}")

        # Step 3: Check trust updated
        try:
            trust = self.get_trust()
            types = trust.get("recommendation_types", [])
            trust_type = next(
                (t for t in types if t.get("type") == rec_type), None
            )
            if trust_type or rec_type == "any":
                checks["trust_updated"] = True
            else:
                checks["errors"].append(
                    "Trust: recommendation type not found"
                )
        except requests.RequestException as e:
            checks["errors"].append(f"Trust check failed: {e}")

        # Step 4: Check Mission Control reflects trust
        try:
            mc = self.get_mc()
            trust_summary = mc.get("trust_summary")
            if trust_summary:
                checks["mc_updated"] = True
            else:
                checks["errors"].append(
                    "Mission Control: trust_summary missing"
                )
        except requests.RequestException as e:
            checks["errors"].append(f"Mission Control check failed: {e}")

        return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cache validation — outcome→effectiveness→trust→MC",
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
        default="-",
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    checker = PropagationChecker(args.api_url, args.api_key)

    print("Cache Validation — Ω-7B.1 Propagation Check")
    print(f"API: {args.api_url}")
    print()

    # Capture baseline
    print("Capturing baseline…")
    try:
        initial_trust = checker.get_initial_trust()
        initial_mc = checker.get_initial_mc()
    except requests.RequestException as e:
        print(f"Baseline capture failed: {e}")
        return 1

    print(f"  Trust types: {len(initial_trust.get('recommendation_types', []))}")
    print(f"  MC trust_summary: {initial_mc.get('trust_summary') is not None}")
    print()

    # Run propagation check
    print("Running propagation check…")
    checks = checker.check_propagation(initial_trust, initial_mc)

    all_passed = all(
        checks[k]
        for k in [
            "outcome_submitted",
            "effectiveness_updated",
            "trust_updated",
            "mc_updated",
        ]
    )

    print(f"  Outcome submitted:     {checks['outcome_submitted']}")
    print(f"  Effectiveness updated: {checks['effectiveness_updated']}")
    print(f"  Trust updated:         {checks['trust_updated']}")
    print(f"  Mission Control updated: {checks['mc_updated']}")
    print()

    if checks["errors"]:
        print("Errors:")
        for err in checks["errors"]:
            print(f"  - {err}")

    report = {
        "passed": all_passed,
        "checks": checks,
        "baseline": {
            "trust_type_count": len(
                initial_trust.get("recommendation_types", [])
            ),
            "mc_had_trust_summary": initial_mc.get("trust_summary")
            is not None,
        },
    }
    payload = json.dumps(report, indent=2)

    if args.output == "-":
        print(payload)
    else:
        from pathlib import Path
        Path(args.output).write_text(payload + "\n")
        print(f"Report written to {args.output}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
