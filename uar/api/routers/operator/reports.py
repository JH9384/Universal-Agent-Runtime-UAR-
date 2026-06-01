"""Report Generation router (trust-validation + burnin-24h)."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import _load_all_snapshots
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/reports/trust-validation")
async def get_trust_validation_report(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Generate a human-readable trust validation report."""
    auth_middleware(credentials)

    try:
        from uar.core.trust_engine import compute_trust
        from uar.core.effectiveness_ranking import compute_effectiveness

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = compute_trust(outcomes, metadata)
        eff_result = compute_effectiveness(outcomes, metadata)
        trust_types = trust_result.get("recommendation_types", [])
        eff_types = eff_result.get("recommendation_types", [])

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

        corr = None
        try:
            from scipy.stats import spearmanr

            eff_map = {
                t["type"]: t.get("resolution_rate", 0.0)
                for t in eff_types
                if "type" in t
            }
            ts, rr = [], []
            for t in trust_types:
                tn = t.get("type", "")
                if tn in eff_map:
                    ts.append(t.get("trust_score", 0.0))
                    rr.append(eff_map[tn])
            if len(ts) >= 3:
                c, _ = spearmanr(ts, rr)
                corr = round(float(c), 3) if c is not None else None
        except Exception:
            pass

        drift = [t for t in trust_types if t.get("drift_penalty", 0) > 0]

        narrative_parts = ["Trust Validation Report"]
        if bands["highly_trusted"] + bands["trusted"] > len(trust_types) * 0.5:
            narrative_parts.append("Most types are in the trusted band.")
        if drift:
            narrative_parts.append(
                f"{len(drift)} type(s) showing drift signals."
            )
        if corr is not None:
            narrative_parts.append(f"Outcome correlation is {corr}.")
        else:
            narrative_parts.append("Insufficient data for correlation.")

        return {
            "report_type": "trust_validation",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "trust_distribution": bands,
            "drift_signals": [
                {"type": t["type"], "penalty": t["drift_penalty"]}
                for t in drift
            ],
            "outcome_correlation": corr,
            "type_count": len(trust_types),
            "system_calibration_error": trust_result.get(
                "system_calibration_error"
            ),
        }
    except Exception as exc:
        logger.warning("trust report generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed",
        )


@router.get("/api/uar/reports/burnin-24h")
async def get_burnin_24h_report(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Generate a human-readable 24h burn-in report."""
    auth_middleware(credentials)

    now = int(time.time())
    cutoff = now - 86400

    try:
        snapshots = _load_all_snapshots(limit=24)
        recent = [s for s in snapshots if s.get("timestamp", 0) >= cutoff]

        if not recent:
            return {
                "report_type": "burnin_24h",
                "generated_at": now,
                "narrative": "No snapshots captured in the last 24 hours.",
                "snapshot_count": 0,
                "trust_stable": None,
                "recommendation_growth": None,
            }

        scores = [s.get("recommendation_count", 0) for s in recent]
        trust_counts = [
            len(s.get("trust", {}).get("recommendation_types", []))
            for s in recent
        ]

        first_score = scores[-1] if scores else 0
        last_score = scores[0] if scores else 0
        growth = last_score - first_score

        trust_stable = True
        if len(trust_counts) >= 2:
            first_tc = trust_counts[-1]
            last_tc = trust_counts[0]
            if abs(last_tc - first_tc) > 2:
                trust_stable = False

        narrative_parts = ["24-Hour Burn-In Report"]
        narrative_parts.append(f"{len(recent)} snapshot(s) captured.")
        if growth > 0:
            narrative_parts.append(f"Recommendations increased by {growth}.")
        elif growth < 0:
            narrative_parts.append(
                f"Recommendations decreased by {abs(growth)}."
            )
        else:
            narrative_parts.append("Recommendation count stable.")

        if trust_stable:
            narrative_parts.append("Trust type count stable.")
        else:
            narrative_parts.append("Trust type count changed significantly.")

        return {
            "report_type": "burnin_24h",
            "generated_at": now,
            "narrative": " ".join(narrative_parts),
            "snapshot_count": len(recent),
            "trust_stable": trust_stable,
            "recommendation_growth": growth,
            "latest_recommendation_count": last_score,
            "earliest_recommendation_count": first_score,
        }
    except Exception as exc:
        logger.warning("burnin report generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed",
        )
