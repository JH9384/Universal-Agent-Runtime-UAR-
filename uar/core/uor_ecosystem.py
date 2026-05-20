"""UOR Ecosystem Integration Layer for UAR.

This module provides first-class integration with the UOR Foundation
ecosystem and affiliated projects:

- UOR Foundation (uor.foundation) — core specification
- uor-addr (UOR-Foundation/uor-addr) — content-addressed object identity
- atlas-embeddings (UOR-Foundation/atlas-embeddings) — E8 Lie group embeddings
- prism / prism-btc — data refraction and Bitcoin anchoring
- gethologram.ai — geometric virtual compute
- atomic-lang-model (dkypuros/atomic-lang-model) — formal grammar engine
- moltbook.com/m/uor — community forum
- Project Severance AI (dkypuros/Project_Severance_AI) — AI inference
- Anunix (AdamPippert/Anunix) — self-healing automation OS

Each integration is exposed as a lightweight client that gracefully
degrades to mock/placeholder behaviour when the external service is
unavailable, so UAR pipelines never hard-fail because an optional
ecosystem partner is offline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from .uor_integration import UORObject, ObjectMode, get_uor_integrator

# URL schemes allowed for external ecosystem calls
_ALLOWED_SCHEMES = {"https", "http"}
# Blocked URL patterns (SSRF prevention)
_BLOCKED_HOST_PATTERNS = {
    r"^localhost$",
    r"^127\.",
    r"^10\.",
    r"^172\.(1[6-9]|2[0-9]|3[01])\.",
    r"^192\.168\.",
    r"^169\.254\.",
    r"^0\.0\.0\.0$",
    r"^::1$",
    r"^fc00:",
    r"^fe80:",
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP client helper (shared across ecosystem integrations)
# ---------------------------------------------------------------------------
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

_http_client: Optional[Any] = None


def _get_http_client() -> Any:
    """Get or create a shared httpx client."""
    global _http_client
    if not HTTPX_AVAILABLE:
        return None
    if _http_client is None:
        _http_client = httpx.Client(timeout=30.0)
    return _http_client


def _is_url_safe(url: str) -> bool:
    """Validate URL for SSRF prevention."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return False
        host = parsed.hostname or ""
        for pattern in _BLOCKED_HOST_PATTERNS:
            if re.search(pattern, host, re.IGNORECASE):
                return False
        return True
    except Exception:
        return False


def _http_post(
    url: str, payload: Dict[str, Any], timeout: float = 30.0
) -> Dict[str, Any]:
    """POST JSON to an endpoint with graceful fallback and SSRF guard."""
    if not _is_url_safe(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return {"status": "error", "error": "Unsafe URL blocked", "url": url}
    client = _get_http_client()
    if client is None:
        return {"status": "mock", "note": "httpx not installed"}
    try:
        resp = client.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("HTTP POST to %s failed: %s", url, exc)
        return {"status": "error", "error": str(exc), "url": url}


def _http_get(url: str, timeout: float = 30.0) -> Dict[str, Any]:
    """GET an endpoint with graceful fallback and SSRF guard."""
    if not _is_url_safe(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return {"status": "error", "error": "Unsafe URL blocked", "url": url}
    client = _get_http_client()
    if client is None:
        return {"status": "mock", "note": "httpx not installed"}
    try:
        resp = client.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("HTTP GET to %s failed: %s", url, exc)
        return {"status": "error", "error": str(exc), "url": url}


# ---------------------------------------------------------------------------
# UOR-ADDR Integration
# ---------------------------------------------------------------------------

class UORAddrClient:
    """Client wrapping UOR-ADDR-1 canonicalization and content addressing.

    This is a Python-native implementation aligned with the UOR Foundation
    Rust reference (UOR-Foundation/uor-addr).  It reuses the existing
    ``bounded_json`` module for canonicalization and adds UOR-object
    wrapping on top.
    """

    def __init__(self) -> None:
        self.enabled = True
        self.integrator = get_uor_integrator()

    def canonicalize(self, data: Any) -> Dict[str, Any]:
        """Canonicalize *data* per UOR-ADDR-1 and return envelope."""
        try:
            from uar.uor.bounded_json import canonicalize_json

            canonical_str = canonicalize_json(data)
            canonical_bytes = canonical_str.encode("utf-8")
        except Exception as exc:
            logger.warning("bounded_json canonicalize failed: %s", exc)
            # Fallback: plain JSON with sorted keys
            canonical_bytes = json.dumps(
                data, sort_keys=True, default=str
            ).encode("utf-8")

        digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        return {
            "canonical": canonical_bytes.hex(),
            "digest": digest,
            "size": len(canonical_bytes),
            "mediaType": "application/uor-addr-1+json",
        }

    def resolve(self, digest: str) -> Optional[UORObject]:
        """Resolve a UOR digest via the integrator object cache."""
        return self.integrator.get_object_by_digest(digest)

    def wrap_with_uor(self, data: Any, source: str = "uor-addr") -> UORObject:
        """Canonicalize *data* and wrap as a UOR object."""
        env = self.canonicalize(data)
        uor_obj = UORObject(
            data={"content": data, "addr": env},
            mode=ObjectMode.IMMUTABLE_SINGULAR,
        )
        uor_obj.digest = env["digest"]
        uor_obj.size = env["size"]
        uor_obj.media_type = env["mediaType"]
        uor_obj.add_provenance(source, "uor_addr_canonicalize")
        uor_obj.add_schema_extension("uor_addr_digest", env["digest"])
        uor_obj.add_schema_extension("uor_addr_size", env["size"])

        # Cache for resolve()
        self.integrator.object_cache[env["digest"]] = uor_obj
        return uor_obj


# ---------------------------------------------------------------------------
# Hologram Integration
# ---------------------------------------------------------------------------

class HologramClient:
    """Client for gethologram.ai geometric virtual compute API.

    Hologram unifies compute, memory and networking into a single
    virtual data infrastructure.  This client provides a thin Python
    bridge so UAR skills can submit inference and transformation jobs.

    Configure via env:
        HOLOGRAM_API_KEY   — authentication token
        HOLOGRAM_API_URL   — base URL (default https://api.gethologram.ai)
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("HOLOGRAM_API_KEY", "")
        self.base_url = os.getenv(
            "HOLOGRAM_API_URL", "https://api.gethologram.ai"
        )
        self.enabled = bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def query(self, model_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a geometric inference query."""
        url = f"{self.base_url}/v1/infer"
        payload = {"model_id": model_id, "inputs": inputs}

        client = _get_http_client()
        if client is None:
            return self._mock_query(model_id, inputs)

        try:
            resp = client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Hologram query failed: %s", exc)
            return self._mock_query(model_id, inputs)

    def _mock_query(
        self, model_id: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Graceful mock when Hologram is unreachable."""
        return {
            "status": "mock",
            "model_id": model_id,
            "inputs": inputs,
            "outputs": {"embedding": [0.0] * 128},
            "note": "Hologram API not configured or unreachable",
        }

    def status(self) -> Dict[str, Any]:
        """Check Hologram service health."""
        url = f"{self.base_url}/health"
        client = _get_http_client()
        if client is None:
            return {"status": "mock", "reachable": False}
        try:
            resp = client.get(url, headers=self._headers())
            return {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "reachable": True,
                "status_code": resp.status_code,
            }
        except Exception as exc:
            return {"status": "error", "reachable": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Moltbook Forum Integration
# ---------------------------------------------------------------------------

class MoltbookClient:
    """Client for moltbook.com/m/uor community forum.

    Provides read-only topic listing and search.  Write operations
    (posting) require authentication and are gated behind a
    ``MOLTBOOK_API_KEY`` environment variable.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("MOLTBOOK_API_KEY", "")
        self.base_url = os.getenv(
            "MOLTBOOK_API_URL", "https://moltbook.com/api/v1"
        )

    def list_topics(
        self, category: str = "uor", limit: int = 10
    ) -> Dict[str, Any]:
        """List recent forum topics."""
        url = f"{self.base_url}/topics?category={category}&limit={limit}"
        return _http_get(url)

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search forum posts."""
        url = f"{self.base_url}/search?q={query}&limit={limit}"
        return _http_get(url)

    def post_topic(
        self, title: str, body: str, category: str = "uor"
    ) -> Dict[str, Any]:
        """Post a new topic (requires API key)."""
        if not self.api_key:
            return {
                "status": "error",
                "error": "MOLTBOOK_API_KEY not set",
            }
        url = f"{self.base_url}/topics"
        return _http_post(
            url, {"title": title, "body": body, "category": category}
        )


# ---------------------------------------------------------------------------
# Prism-BTC Integration (placeholder)
# ---------------------------------------------------------------------------

class PrismBTCClient:
    """Placeholder client for afflom/prism-btc Bitcoin anchoring.

    This integration is pending public availability of the prism-btc
    reference implementation.  When available, UAR will support:

    - Anchoring UOR digests to the Bitcoin blockchain
    - Verifying on-chain proof-of-existence for UOR objects
    - PRISM data refraction with BTC settlement
    """

    def __init__(self) -> None:
        self.enabled = False
        self.api_url = os.getenv("PRISM_BTC_API_URL", "")

    def anchor_digest(self, digest: str) -> Dict[str, Any]:
        """Anchor a UOR digest on Bitcoin (not yet implemented)."""
        return {
            "status": "placeholder",
            "digest": digest,
            "note": "prism-btc integration pending public release",
        }

    def verify_anchor(self, digest: str) -> Dict[str, Any]:
        """Verify an on-chain anchor (not yet implemented)."""
        return {
            "status": "placeholder",
            "digest": digest,
            "verified": None,
            "note": "prism-btc integration pending public release",
        }


# ---------------------------------------------------------------------------
# Severance AI Integration (placeholder)
# ---------------------------------------------------------------------------

class SeveranceAIClient:
    """Placeholder client for dkypuros/Project_Severance_AI.

    When the project repository becomes publicly available this client
    will provide:

    - Modular AI inference with separation-of-concerns
    - Runtime model swapping without pipeline restart
    - Formal verification hooks for AI outputs
    """

    def __init__(self) -> None:
        self.enabled = False
        self.service_url = os.getenv("SEVERANCE_AI_URL", "")

    def infer(self, prompt: str, model: str = "default") -> Dict[str, Any]:
        """Run inference via Severance AI (placeholder)."""
        return {
            "status": "placeholder",
            "prompt": prompt,
            "model": model,
            "note": "Severance AI integration pending public release",
        }

    def verify_output(
        self, output: str, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify an inference output against formal criteria."""
        return {
            "status": "placeholder",
            "output": output,
            "criteria": criteria,
            "verified": None,
            "note": "Severance AI integration pending public release",
        }


# ---------------------------------------------------------------------------
# UOR Foundation Live API Integration
# ---------------------------------------------------------------------------

class UORFoundationClient:
    """Client for the live UOR Foundation API (api.uor.foundation).

    Provides verification and discovery against the reference
    UOR Foundation runtime endpoint.

    Configure via env:
        UOR_FOUNDATION_API_URL  — base URL (default
        https://api.uor.foundation/v1)
    """

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "UOR_FOUNDATION_API_URL",
            "https://api.uor.foundation/v1",
        )
        self.enabled = True

    def verify(self, x: int = 42) -> Dict[str, Any]:
        """Call the UOR Foundation kernel verify endpoint.

        Args:
            x: integer parameter for the verify op (default 42)
        """
        url = f"{self.base_url}/kernel/op/verify?x={x}"
        return _http_get(url, timeout=10.0)

    def status(self) -> Dict[str, Any]:
        """Check UOR Foundation API health."""
        url = f"{self.base_url}/health"
        result = _http_get(url, timeout=10.0)
        if result.get("status") == "mock":
            return {
                "status": "unconfigured",
                "reachable": False,
                "note": "httpx not installed or network unreachable",
            }
        return result


# ---------------------------------------------------------------------------
# Anunix Integration (placeholder)
# ---------------------------------------------------------------------------

class AnunixClient:
    """Placeholder client for AdamPippert/Anunix self-healing automation OS.

    When the project repository becomes publicly available this client
    will provide:

    - Remote shell/command execution on Anunix-managed hosts
    - Health-check polling for self-healing infrastructure
    - Automated remediation trigger API
    """

    def __init__(self) -> None:
        self.enabled = False
        self.api_url = os.getenv("ANUNIX_API_URL", "")
        self.api_key = os.getenv("ANUNIX_API_KEY", "")

    def health_check(self, host_id: str) -> Dict[str, Any]:
        """Check health of an Anunix-managed host (placeholder)."""
        return {
            "status": "placeholder",
            "host_id": host_id,
            "healthy": None,
            "note": "Anunix integration pending public release",
        }

    def run_command(self, host_id: str, command: str) -> Dict[str, Any]:
        """Execute a command on an Anunix host (placeholder)."""
        return {
            "status": "placeholder",
            "host_id": host_id,
            "command": command,
            "stdout": "",
            "stderr": "",
            "note": "Anunix integration pending public release",
        }


# ---------------------------------------------------------------------------
# Ecosystem Coordinator
# ---------------------------------------------------------------------------

class UOREcosystem:
    """Unified coordinator for all UOR ecosystem integrations."""

    def __init__(self) -> None:
        self.uor_addr = UORAddrClient()
        self.hologram = HologramClient()
        self.moltbook = MoltbookClient()
        self.prism_btc = PrismBTCClient()
        self.severance_ai = SeveranceAIClient()
        self.anunix = AnunixClient()
        self.uor_foundation = UORFoundationClient()

    def status(self) -> Dict[str, Any]:
        """Return health/status for every ecosystem integration.

        Where possible, performs an actual lightweight ping to verify
        network reachability (not just configuration state).
        """
        # UOR Foundation — actually try to reach the API
        foundation_ping = self.uor_foundation.status()
        foundation_reachable = (
            foundation_ping.get("status_code") == 200
            or foundation_ping.get("status") == "ok"
        )

        # Hologram — lightweight health check if key is present
        hologram_ping = (
            self.hologram.status()
            if self.hologram.enabled
            else {"status": "not_configured"}
        )

        return {
            "uor_addr": {"enabled": self.uor_addr.enabled},
            "hologram": {
                "enabled": self.hologram.enabled,
                "configured": bool(self.hologram.api_key),
                "reachable": hologram_ping.get("status") == "ok",
            },
            "moltbook": {
                "enabled": bool(self.moltbook.api_key),
            },
            "prism_btc": {"enabled": self.prism_btc.enabled},
            "severance_ai": {"enabled": self.severance_ai.enabled},
            "anunix": {"enabled": self.anunix.enabled},
            "uor_foundation": {
                "enabled": self.uor_foundation.enabled,
                "reachable": foundation_reachable,
                "ping": foundation_ping,
            },
        }


# Global instance
_ecosystem: Optional[UOREcosystem] = None


def get_uor_ecosystem() -> UOREcosystem:
    """Get the global UOR ecosystem coordinator."""
    global _ecosystem
    if _ecosystem is None:
        _ecosystem = UOREcosystem()
    return _ecosystem


def reset_uor_ecosystem() -> None:
    """Reset the global ecosystem coordinator (useful for testing)."""
    global _ecosystem
    _ecosystem = None
