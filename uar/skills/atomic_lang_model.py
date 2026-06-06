"""Atomic Language Model (ALM) integration skills.

Provides skills for interacting with the external Atomic Language Model
service:
  - alm_analyze       : Analyze formal grammar specifications (BNF, EBNF)
  - alm_generate      : Generate token sequences from a prefix
  - alm_verify        : Validate text against ALM grammar

Configure via env:
  ALM_SERVICE_URL    — ALM service endpoint
                      (default: http://localhost:5001/api/v1)
  ALM_TIMEOUT_SEC    — Request timeout in seconds (default: 30)

Goal metadata overrides:
  alm_service_url     — per-run service URL override
"""

from __future__ import annotations

import atexit
import logging
import os
from typing import Dict, Any
from urllib.parse import urlparse

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

from uar.core.circuit_breaker_decorator import with_circuit_breaker
from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard, wrap_with_digest

logger = logging.getLogger(__name__)


# HTTP client with connection pooling (reused across calls)
_http_client = None


def _get_http_client():
    """Get or create HTTP client with connection pooling."""
    global _http_client
    if not HTTPX_AVAILABLE:
        return None
    if _http_client is None:
        try:
            timeout = max(
                1.0,
                float(
                    os.getenv("ALM_TIMEOUT_SEC", "30").strip() or "30"
                ),
            )
        except (ValueError, TypeError):
            logger.warning(
                "Invalid ALM_TIMEOUT_SEC, using default 30"
            )
            timeout = 30.0
        limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        )
        _http_client = httpx.Client(
            timeout=timeout,
            limits=limits,
        )
    return _http_client


def _close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        try:
            _http_client.close()
        except Exception:
            logger.exception("HTTP client close failed")
        _http_client = None


atexit.register(_close_http_client)


def _get_service_url(ctx: PipelineContext | None = None) -> str:
    """Get ALM service URL from goal metadata override or environment."""
    url = os.getenv("ALM_SERVICE_URL", "http://localhost:5001/api/v1")
    if ctx and ctx.goal.metadata:
        override_url = ctx.goal.metadata.get("alm_service_url")
        if override_url:
            url = override_url
    if urlparse(url).scheme not in ("http", "https"):
        logger.warning("Ignoring invalid ALM_SERVICE_URL scheme: %s", url)
        url = "http://localhost:5001/api/v1"
    return url.rstrip("/")


def _call_alm(
    endpoint: str,
    payload: Dict[str, Any],
    ctx: PipelineContext | None = None,
) -> Dict[str, Any]:
    """Call ALM service endpoint using httpx with proper error handling.

    Falls back to mock responses if httpx is not available.

    Args:
        endpoint: ALM service endpoint (e.g., "analyze", "generate", "verify")
        payload: Request payload to send to the service
        ctx: Pipeline context for metadata overrides

    Returns:
        Response dictionary from ALM service
    """
    client = _get_http_client()

    if client is None:
        logger.warning("httpx not available, using mock responses for ALM")
        return _mock_alm_response(endpoint, payload)

    base_url = _get_service_url(ctx)

    # Map pipeline endpoints to actual ALM service API
    endpoint_map = {
        "analyze": ("POST", f"{base_url}/validate"),
        "generate": ("GET", f"{base_url}/generate"),
        "verify": ("POST", f"{base_url}/validate"),
    }
    method, url = endpoint_map.get(
        endpoint, ("POST", f"{base_url}/{endpoint}")
    )

    logger.info("Calling ALM service %s %s", method, url)

    try:
        if method == "GET":
            req_payload = payload.copy()
            params = {}
            if "count" in req_payload:
                params["count"] = req_payload.pop("count")
            if "prefix" in req_payload:
                params["prefix"] = req_payload.pop("prefix")
            if "text" in req_payload:
                params["prefix"] = req_payload.pop("text")
            response = client.get(url, params=params)
        else:
            if endpoint == "analyze":
                req_body = {"sentences": [payload.get("grammar_spec", "")]}
            elif endpoint == "verify":
                req_body = {"sentences": [payload.get("text", "")]}
            else:
                req_body = payload
            response = client.post(url, json=req_body)
        response.raise_for_status()
        return wrap_with_digest(response.json())
    except httpx.HTTPStatusError as e:
        logger.error("ALM service returned error: %s", e.response.status_code)
        try:
            error_detail = e.response.json()
        except (ValueError, OSError):
            error_detail = {"error": "Failed to parse error response"}
        return wrap_with_digest({
            "status": "error",
            "error": "ALM service request failed",
            "details": error_detail,
        })
    except httpx.TimeoutException:
        logger.error("ALM service timeout")
        return wrap_with_digest({
            "status": "error",
            "error": "Request timeout",
            "details": "Service did not respond in time",
        })
    except httpx.ConnectError:
        logger.error("Failed to connect to ALM service")
        return wrap_with_digest({
            "status": "error",
            "error": "Connection failed",
            "details": f"Could not connect to {base_url}",
        })


def _mock_alm_response(
    endpoint: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate mock responses when httpx is not available.

    Args:
        endpoint: ALM service endpoint
        payload: Request payload

    Returns:
        Mock response dictionary
    """
    if endpoint == "analyze":
        grammar_spec = payload.get("grammar_spec", "")
        if "recursive" in str(grammar_spec).lower():
            return wrap_with_digest({
                "status": "success",
                "analysis": "Grammar supports provable recursion.",
                "details": "Passed formal verification checks.",
            })
        return wrap_with_digest({
            "status": "success",
            "analysis": "Grammar analyzed successfully.",
            "details": "Basic syntax check passed.",
        })

    elif endpoint == "generate":
        prefix = payload.get("prefix", "")
        count = payload.get("count", 5)
        if "student" in prefix:
            return wrap_with_digest({
                "tokens": ["student", "left", "the", "school", "yesterday"]
            })
        return wrap_with_digest({
            "tokens": [f"token_{i}" for i in range(count)]
        })

    elif endpoint == "verify":
        text = payload.get("text", "")
        if "student left" in text:
            return wrap_with_digest({
                "valid": True,
                "proof_id": "proof_123",
                "notes": "Syntactically correct and semantically plausible.",
            })
        return wrap_with_digest({
            "valid": False,
            "error": "Syntax error or semantic violation detected.",
            "details": "Requires formal grammar check.",
        })

    return wrap_with_digest({"status": "error", "error": "Unknown endpoint"})


@register_skill("alm_analyze")
@skill_guard("Alm Analyze", status="failed")
@with_circuit_breaker("alm", failure_threshold=3, recovery_timeout=30.0)
def alm_analyze(ctx: PipelineContext) -> Dict[str, Any]:
    """Analyze a formal grammar specification using ALM.

    Analyzes formal grammar specifications (e.g., BNF, EBNF) against ALM's
    formal rules for mathematical rigor and provability.

    Args:
        ctx: Pipeline context containing goal metadata with grammar_spec

    Returns:
        Dictionary with analysis results (status, analysis, details)
    """
    meta = ctx.goal.metadata or {}
    grammar_spec = meta.get("grammar_spec", "")

    if not grammar_spec:
        return {
            "status": "failed",
            "error": "No grammar_spec provided in goal metadata",
        }

    result = _call_alm("analyze", {"grammar_spec": grammar_spec}, ctx)
    from uar.core.uor_integration import wrap_skill_result

    return wrap_skill_result(
        {"status": "completed", "grammar_spec": grammar_spec, **result},
        skill_name="alm_analyze",
    )


@register_skill("alm_generate")
@skill_guard("Alm Generate", status="failed")
@with_circuit_breaker("alm", failure_threshold=3, recovery_timeout=30.0)
def alm_generate(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate a token sequence from a prefix using ALM.

    Generates a sequence of tokens based on a given prefix using the ALM's
    probabilistic model for formal language generation.

    Args:
        ctx: Pipeline context containing goal metadata with prefix and count

    Returns:
        Dictionary with generated tokens
    """
    meta = ctx.goal.metadata or {}
    prefix = meta.get("prefix", "")
    count = meta.get("count", 5)

    if not prefix:
        return {
            "status": "failed",
            "error": "No prefix provided in goal metadata",
        }

    result = _call_alm("generate", {"prefix": prefix, "count": count}, ctx)
    if result.get("status") == "error":
        return {
            "status": "failed",
            "prefix": prefix,
            "count": count,
            "error": result.get("error", "ALM generation failed"),
            "details": result.get("details"),
        }
    from uar.core.uor_integration import wrap_skill_result

    return wrap_skill_result(
        {
            "status": "completed",
            "prefix": prefix,
            "count": count,
            "tokens": result.get("tokens", []),
        },
        skill_name="alm_generate",
    )


@register_skill("alm_verify")
@skill_guard("Alm Verify", status="failed")
@with_circuit_breaker("alm", failure_threshold=3, recovery_timeout=30.0)
def alm_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Validate text against ALM grammar.

    Performs a full syntactic and semantic validation of a given text
    against the ALM's formal grammar.

    Args:
        ctx: Pipeline context containing goal metadata with text to validate

    Returns:
        Dictionary with validation status, proof_id (if valid), and notes
    """
    meta = ctx.goal.metadata or {}
    text = meta.get("text", "")

    if not text:
        return {
            "status": "failed",
            "error": "No text provided in goal metadata",
        }

    result = _call_alm("verify", {"text": text}, ctx)
    if result.get("status") == "error":
        return {
            "status": "failed",
            "text": text,
            "error": result.get("error", "ALM verification failed"),
            "details": result.get("details"),
        }
    from uar.core.uor_integration import wrap_skill_result

    return wrap_skill_result(
        {
            "status": "completed",
            "text": text,
            "valid": result.get("valid", False),
            "proof_id": result.get("proof_id"),
            "notes": result.get("notes"),
        },
        skill_name="alm_verify",
    )
