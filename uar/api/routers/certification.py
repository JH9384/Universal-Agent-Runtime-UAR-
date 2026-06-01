"""Certification API endpoint for the UAR Trust Spine.

Trust Spine Phase: T4
Issues: #57, #70
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.core.certification import certify_runtime
from uar.core.runtime_health import build_runtime_snapshot

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.get("/api/uar/certification")
async def get_certification(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return a Certification report combining T1, T2, and T3 evidence.

    Derives:
    - Replay confidence from the most recent run in the store.
    - Runtime health from store + registry + latest burn-in.
    - Burn-in from the last executed burn-in report (if any).
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    from uar.api.server import store
    from uar.core.registry import registry
    from uar.core.runtime_health import score_runtime_health
    from uar.core.replay_confidence import score_replay
    from uar.memory.base_store import run_record_from_dict
    from uar.api.routers.burn_in import BurnInProxy

    burnin_proxy = BurnInProxy.from_latest(store=store)
    snapshot = build_runtime_snapshot(store)

    rh_report = score_runtime_health(
        registry=registry,
        burnin_report=burnin_proxy,
        snapshot=snapshot,
    )

    replay_score = None
    try:
        if snapshot.latest_record is not None:
            run_record = run_record_from_dict(snapshot.latest_record)
            rc = score_replay(run_record)
            replay_score = rc.score
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Failed to score replay confidence: %s", exc
        )

    cert = certify_runtime(
        replay_confidence_score=replay_score,
        burnin_report=burnin_proxy,
        runtime_health_score=rh_report.score,
    )
    return cert.to_dict()
