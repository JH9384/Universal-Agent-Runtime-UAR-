"""Burn-In API endpoints for the UAR Trust Spine.

Trust Spine Phase: T3
Issue: #62
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware

security = HTTPBearer(auto_error=False)

router = APIRouter()
logger = logging.getLogger(__name__)

# Metadata key used for store persistence (Issue #86).
BURNIN_REPORT_KEY = "__burnin_latest__"

# Thread-safe latest-report slot.
# Write protected by _report_lock so concurrent POST /burnin/run calls
# in a multi-threaded server cannot corrupt the stored value.
_report_lock = threading.RLock()
_latest_report: Optional[dict] = None


class BurnInProxy:
    """Lightweight adapter from a stored burn-in report dict to the
    duck-typed interface expected by score_runtime_health and
    certify_runtime.

    Used by runtime_health, certification, and mission_control routers
    so that the adapter is defined exactly once.
    """

    __slots__ = ("score", "passed")

    def __init__(self, d: dict) -> None:
        try:
            self.score: int = int(d.get("score", 0))
        except (TypeError, ValueError):
            self.score = 0
        self.passed: bool = bool(d.get("passed", False))

    @classmethod
    def from_latest(
        cls, store: Optional[object] = None
    ) -> Optional["BurnInProxy"]:
        """Return a BurnInProxy for the current report, or None.

        Issue #86: when the in-process slot is empty (e.g. after
        restart) and a store is provided, recover from the persisted
        uar_metadata row before returning None.

        TOCTOU fix: after reading from the store we re-acquire the lock
        and only write back if the slot is still None.  This prevents
        a concurrent _set_latest_report (which ran while we were
        querying the store) from being overwritten by stale store data.
        """
        global _latest_report
        with _report_lock:
            report = _latest_report

        if report is None and store is not None:
            if not hasattr(store, "get_metadata"):
                logger.warning(
                    "BurnInProxy.from_latest: store missing get_metadata"
                )
                return None
            if not callable(getattr(store, "get_metadata", None)):
                logger.warning(
                    "BurnInProxy.from_latest: store.get_metadata not callable"
                )
                return None
            try:
                stored = store.get_metadata(BURNIN_REPORT_KEY)
            except Exception:
                stored = None
            if stored is not None:
                with _report_lock:
                    if _latest_report is None:
                        _latest_report = dict(stored)
                        report = _latest_report  # Use the value we just wrote
                    else:
                        report = _latest_report  # Use fresher value

        return cls(report) if report is not None else None

    @classmethod
    def snapshot_latest(
        cls, store: Optional[object] = None
    ) -> "tuple[Optional[BurnInProxy], Optional[dict]]":
        """Return (proxy, raw_dict) in a single atomic read.

        Bug fix: callers that need to return the raw dict (e.g.
        get_latest_burnin) must capture it in the same operation as
        the proxy check to avoid TOCTOU races with _set_latest_report.

        TOCTOU fix: same compare-and-set pattern as from_latest —
        only write back the store value when the slot is still None.
        """
        global _latest_report
        with _report_lock:
            report = _latest_report

        if report is None and store is not None:
            if not hasattr(store, "get_metadata"):
                logger.warning(
                    "BurnInProxy.snapshot_latest: store missing get_metadata"
                )
                return None, None
            if not callable(getattr(store, "get_metadata", None)):
                logger.warning(
                    "BurnInProxy.snapshot_latest: store.get_metadata "
                    "not callable"
                )
                return None, None
            try:
                stored = store.get_metadata(BURNIN_REPORT_KEY)
            except Exception:
                stored = None
            if stored is not None:
                with _report_lock:
                    if _latest_report is None:
                        _latest_report = dict(stored)
                        report = _latest_report  # Use the value we just wrote
                    else:
                        report = _latest_report  # Use fresher value

        if report is None:
            return None, None
        return cls(report), dict(report)


def _set_latest_report(
    report_dict: dict,
    store: Optional[object] = None,
) -> bool:
    """Write _latest_report under lock and persist to store.

    Issue #86: when a store is provided the report is also written to
    uar_metadata so it survives restart, worker replacement, and
    container redeployment.

    The store write is done *outside* the lock so slow I/O does not
    block readers of _latest_report (e.g. health-check endpoints).

    Returns:
        True if persistence succeeded (or no store was provided),
        False if the store write failed.
    """
    global _latest_report
    with _report_lock:
        _latest_report = report_dict

    persisted = True
    if store is not None:
        try:
            store.put_metadata(BURNIN_REPORT_KEY, report_dict)
        except Exception as exc:
            logger.warning(
                "Failed to persist burn-in report to store: %s", exc
            )
            persisted = False
    return persisted


@router.get("/api/uar/burnin/latest")
async def get_latest_burnin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Return the most recent burn-in report, or 404 if none exists.

    Issue #86: falls back to store on cache miss so restarts do not
    lose the last completed evidence.

    Bug fix: proxy and raw dict are captured in one atomic read via
    snapshot_latest() to prevent TOCTOU races with _set_latest_report.
    """
    from uar.api.server import store as _store

    proxy, raw = BurnInProxy.snapshot_latest(store=_store)
    if proxy is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "error": "not_found",
                    "message": "No burn-in report available",
                }
            },
        )
    return raw


@router.post("/api/uar/burnin/run")
async def run_burnin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security
    ),
):
    """Execute a smoke burn-in in direct mode and return the report.

    Requires admin tier.  In dev mode any authenticated user may trigger.
    """
    from uar.api.middleware import is_dev_mode

    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )
    is_admin = user_info.get("tier") == "admin"
    if not is_admin and not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "Admin access required",
            },
        )

    from uar.api.server import store
    from uar.core.registry import registry
    from uar.testing.burnin.runner import BurnInRunner

    runner = BurnInRunner(
        mode="direct",
        store=store,
        registry=registry,
    )
    report = runner.run_smoke()
    report_dict = report.to_dict()
    persisted = _set_latest_report(report_dict, store=store)
    if not persisted:
        report_dict["persisted"] = False
        report_dict["warning"] = (
            "Burn-in report was not persisted to store; "
            "it will be lost on restart."
        )
    return JSONResponse(status_code=200, content=report_dict)
