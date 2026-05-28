"""Metrics and provenance endpoints.

Extracted from server.py to reduce monolith size.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import security
from uar.api.metrics import get_metrics_collector

router = APIRouter()


def _check_metrics_auth(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> None:
    """Require Bearer token if METRICS_API_KEY is configured."""
    expected = os.getenv("METRICS_API_KEY", "").strip()
    if not expected:
        return
    token = (
        credentials.credentials
        if credentials and credentials.scheme == "Bearer"
        else ""
    )
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized",
                "message": "Valid metrics API key required",
            },
        )


@router.get("/api/metrics")
async def metrics_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Prometheus-compatible metrics endpoint."""
    _check_metrics_auth(credentials)
    metrics = get_metrics_collector()
    return Response(
        content=metrics.get_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/api/metrics/json")
async def metrics_json_endpoint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """JSON metrics endpoint for debugging."""
    _check_metrics_auth(credentials)
    metrics = get_metrics_collector()
    return metrics.get_metrics()


@router.get("/metrics")
async def prometheus_metrics(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Prometheus metrics endpoint for scraping."""
    _check_metrics_auth(credentials)
    from uar.api.uor_alignment_metrics import get_uor_alignment_metrics

    collector = get_metrics_collector()
    body = collector.get_prometheus_format()

    # Append UOR alignment metrics
    uor_metrics = get_uor_alignment_metrics()
    body += uor_metrics.get_prometheus_metrics()

    return Response(content=body, media_type="text/plain")
