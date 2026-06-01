"""Trust Explorer router."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/trust-explorer/{rec_type}")
async def get_trust_explorer(
    rec_type: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Detailed trust breakdown for a single recommendation type."""
    auth_middleware(credentials)

    try:
        from uar.core.trust_engine import compute_trust
        from uar.core.effectiveness_ranking import compute_effectiveness
        from uar.core.evidence import aggregate_evidence
        from uar.core.calibration import compute_calibration

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)

        trust_result = compute_trust(outcomes, metadata)
        type_data = None
        for t in trust_result.get("recommendation_types", []):
            if t.get("type") == rec_type:
                type_data = t
                break

        if not type_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Type '{rec_type}' not found",
            )

        eff = compute_effectiveness(outcomes, metadata)
        eff_type = next(
            (
                e
                for e in eff.get("recommendation_types", [])
                if e.get("type") == rec_type
            ),
            {},
        )

        cal = compute_calibration(outcomes, metadata)
        cal_type = next(
            (c for c in cal.get("types", []) if c.get("type") == rec_type),
            {},
        )

        ev = aggregate_evidence(outcomes, metadata)
        ev_type = next(
            (
                e
                for e in ev.get("recommendation_types", [])
                if e.get("type") == rec_type
            ),
            {},
        )

        return {
            "type": rec_type,
            "trust_score": type_data.get("trust_score"),
            "effectiveness": {
                "score": eff_type.get("weighted_resolution_rate"),
                "resolved": eff_type.get("resolved_count", 0),
                "total": eff_type.get("total_count", 0),
                "drift_penalty": eff_type.get("drift_penalty", 0),
            },
            "calibration": {
                "score": cal_type.get("calibration_score"),
                "error": cal_type.get("calibration_error"),
                "bucket": cal_type.get("bucket"),
            },
            "evidence": {
                "score": ev_type.get("evidence_score"),
                "sample_size": ev_type.get("sample_size", 0),
                "resolution_rate": ev_type.get("resolution_rate"),
            },
            "generated_at": int(time.time()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trust explorer failed for %s: %s", rec_type, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trust computation failed",
        )
