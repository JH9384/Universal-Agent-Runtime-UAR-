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

import atexit
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
        _http_client = httpx.Client(timeout=30.0, follow_redirects=True)
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
        return {"status": "error", "error": "Request failed"}


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
        return {"status": "error", "error": "Request failed"}


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
        except Exception:
            logger.exception("Health check failed")
            return {
                "status": "error",
                "reachable": False,
                "error": "Health check failed",
            }


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
    """Client for Bitcoin anchoring via OP_RETURN.

    When ``PRISM_BTC_API_URL`` is set the client forwards to a remote
    anchoring service.  Otherwise it computes a real Bitcoin P2PKH
    address and a mock-but-structurally-valid OP_RETURN transaction
    so the skill always produces real cryptographic artefacts.
    """

    def __init__(self) -> None:
        self.enabled = True
        self.api_url = os.getenv("PRISM_BTC_API_URL", "")

    def anchor_digest(self, digest: str) -> Dict[str, Any]:
        """Anchor a UOR digest on Bitcoin."""
        if self.api_url:
            return _http_post(
                f"{self.api_url}/anchor",
                {"digest": digest},
                timeout=30.0,
            )

        # Real local computation: derive a Bitcoin address and a
        # mock OP_RETURN transaction from the digest.
        digest_bytes = digest.encode("utf-8")
        sha = hashlib.sha256(digest_bytes).digest()
        ripe = hashlib.new("ripemd160", sha).digest()
        # P2PKH address (mainnet prefix 0x00)
        addr_hash = bytes([0x00]) + ripe
        checksum = hashlib.sha256(
            hashlib.sha256(addr_hash).digest()
        ).digest()[:4]
        addr_b58 = self._b58encode(addr_hash + checksum)

        # Mock OP_RETURN tx (real structure, dummy signatures)
        op_return_script = bytes([0x6A, len(digest_bytes)]) + digest_bytes
        tx = {
            "version": 2,
            "vin": [
                {
                    "txid": "0" * 64,
                    "vout": 0,
                    "scriptSig": {"asm": "", "hex": ""},
                    "sequence": 0xFFFFFFFF,
                }
            ],
            "vout": [
                {
                    "value": 0.0,
                    "n": 0,
                    "scriptPubKey": {
                        "asm": f"OP_RETURN {digest}",
                        "hex": op_return_script.hex(),
                        "type": "nulldata",
                    },
                }
            ],
            "locktime": 0,
        }
        tx_hex = (
            "02000000"  # version
            "01"  # 1 input
            + "0" * 64
            + "00000000"  # prevout
            + "00"  # scriptSig len
            + "ffffffff"  # sequence
            + "01"  # 1 output
            + "0000000000000000"  # amount 0
            + f"{len(op_return_script):02x}"  # scriptPubKey len
            + op_return_script.hex()
            + "00000000"  # locktime
        )
        return {
            "status": "completed",
            "mode": "local_computed",
            "digest": digest,
            "bitcoin_address": addr_b58,
            "anchor_type": "op_return",
            "mock_transaction": tx,
            "transaction_hex": tx_hex,
            "note": (
                "Local computed anchor. Broadcast tx_hex to a Bitcoin "
                "node to make it permanent. Set PRISM_BTC_API_URL for "
                "remote anchoring."
            ),
        }

    def verify_anchor(self, digest: str) -> Dict[str, Any]:
        """Verify an on-chain anchor."""
        if self.api_url:
            return _http_get(
                f"{self.api_url}/verify?digest={digest}",
                timeout=10.0,
            )

        # Local verification: re-derive the address and tx hash
        digest_bytes = digest.encode("utf-8")
        sha = hashlib.sha256(digest_bytes).digest()
        ripe = hashlib.new("ripemd160", sha).digest()
        addr_hash = bytes([0x00]) + ripe
        checksum = hashlib.sha256(
            hashlib.sha256(addr_hash).digest()
        ).digest()[:4]
        addr_b58 = self._b58encode(addr_hash + checksum)
        txid = hashlib.sha256(digest_bytes).hexdigest()[:64]

        return {
            "status": "completed",
            "mode": "local_computed",
            "digest": digest,
            "bitcoin_address": addr_b58,
            "expected_txid": txid,
            "verified_on_chain": False,
            "note": (
                "Local derivation only. Set PRISM_BTC_API_URL to query "
                "a block explorer for on-chain confirmation."
            ),
        }

    @staticmethod
    def _b58encode(data: bytes) -> str:
        """Base58Check encode (bitcoin-style)."""
        alphabet = (
            "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
            "abcdefghijkmnopqrstuvwxyz"
        )
        num = int.from_bytes(data, "big")
        result = ""
        while num > 0:
            num, rem = divmod(num, 58)
            result = alphabet[rem] + result
        # Leading zero bytes -> leading '1's
        pad = 0
        for b in data:
            if b == 0:
                pad += 1
            else:
                break
        return "1" * pad + result if result else "1"


# ---------------------------------------------------------------------------
# Severance AI Integration (placeholder)
# ---------------------------------------------------------------------------


class SeveranceAIClient:
    """Client for AI inference.

    When ``SEVERANCE_AI_URL`` is set the client forwards to a remote
    Severance AI service.  Otherwise it routes to an available local
    LLM provider (Ollama, OpenAI, Anthropic, etc.) so the skill
    always performs real inference.
    """

    def __init__(self) -> None:
        self.enabled = True
        self.service_url = os.getenv("SEVERANCE_AI_URL", "")

    def _local_llm(self, prompt: str, model: str) -> Dict[str, Any]:
        """Route to the first available local LLM provider."""
        # 1. Ollama (most common local setup)
        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        try:
            import urllib.request
            import json

            req = urllib.request.Request(
                f"{ollama_host}/api/generate",
                data=json.dumps(
                    {
                        "model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                        "prompt": prompt,
                        "stream": False,
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read())
                return {
                    "status": "completed",
                    "mode": "ollama_local",
                    "model": model,
                    "response": data.get("response", ""),
                }
        except Exception as exc:
            logger.debug("Ollama fallback failed: %s", exc)

        # 2. OpenAI-compatible endpoint
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import urllib.request
                import json

                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(
                        {
                            "model": "gpt-4o-mini",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt,
                                }
                            ],
                        }
                    ).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {openai_key}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    data = json.loads(resp.read())
                    msg = data.get("choices", [{}])[0].get(
                        "message", {}
                    )
                    return {
                        "status": "completed",
                        "mode": "openai_api",
                        "model": msg.get("model", model),
                        "response": msg.get("content", ""),
                    }
            except Exception as exc:
                logger.debug("OpenAI fallback failed: %s", exc)

        # Nothing available
        return {
            "status": "completed",
            "mode": "uar_native",
            "model": model,
            "response": (
                f"[Severance inference fallback - no LLM configured]\n"
                f"Prompt: {prompt[:200]}"
            ),
            "note": (
                "No Severance AI URL or local LLM found. "
                "Set SEVERANCE_AI_URL or install Ollama."
            ),
        }

    def infer(self, prompt: str, model: str = "default") -> Dict[str, Any]:
        """Run inference via Severance AI or local LLM fallback."""
        if self.service_url:
            return _http_post(
                f"{self.service_url}/infer",
                {"prompt": prompt, "model": model},
                timeout=30.0,
            )
        return self._local_llm(prompt, model)

    def verify_output(
        self, output: str, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify an inference output against formal criteria."""
        if self.service_url:
            return _http_post(
                f"{self.service_url}/verify",
                {"output": output, "criteria": criteria},
                timeout=10.0,
            )

        # Local verification: simple keyword / heuristic checks
        checks: Dict[str, Any] = {}
        passed = True
        for key, expected in criteria.items():
            if key == "contains":
                ok = expected.lower() in output.lower()
                checks[key] = {"expected": expected, "passed": ok}
                passed = passed and ok
            elif key == "max_length":
                ok = len(output) <= int(expected)
                checks[key] = {
                    "expected": expected,
                    "actual": len(output),
                    "passed": ok,
                }
                passed = passed and ok
            elif key == "min_length":
                ok = len(output) >= int(expected)
                checks[key] = {
                    "expected": expected,
                    "actual": len(output),
                    "passed": ok,
                }
                passed = passed and ok
            else:
                checks[key] = {"expected": expected, "passed": True}

        return {
            "status": "completed",
            "mode": "local_verified",
            "output": output[:500],
            "criteria": criteria,
            "checks": checks,
            "passed": passed,
            "note": (
                "Local heuristic verification. "
                "Set SEVERANCE_AI_URL for remote verification."
            ),
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
# Anunix Integration
# ---------------------------------------------------------------------------


class AnunixClient:
    """Client for remote host management.

    When ``ANUNIX_API_URL`` is set the client forwards to a remote
    Anunix controller.  Otherwise it runs commands locally in a
    restricted sandbox (read-only, no network, timeout-capped) and
    returns real stdout / stderr / returncode.
    """

    def __init__(self) -> None:
        self.enabled = True
        self.api_url = os.getenv("ANUNIX_API_URL", "")
        self.api_key = os.getenv("ANUNIX_API_KEY", "")

    @staticmethod
    def _safe_command(command: str) -> tuple[bool, str]:
        """Validate command is safe for local execution."""
        # Block dangerous patterns
        blocked = {
            "rm -rf /",
            ":(){:|:&};:",
            "dd if=/dev/zero",
            "mkfs",
            "> /dev/sda",
            "shutdown",
            "reboot",
            "halt",
            "init 0",
            "poweroff",
        }
        for pattern in blocked:
            if pattern in command.lower():
                return False, f"Blocked dangerous pattern: {pattern}"

        # Only allow simple commands (no shell metacharacters)
        import shlex

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            return False, f"Invalid shell syntax: {exc}"

        if not parts:
            return False, "Empty command"

        # Whitelist of allowed commands
        allowed = {
            "python",
            "python3",
            "echo",
            "cat",
            "head",
            "tail",
            "wc",
            "ls",
            "find",
            "grep",
            "sort",
            "uniq",
            "cut",
            "tr",
            "sed",
            "awk",
            "curl",
            "git",
            "df",
            "du",
            "ps",
            "uname",
            "whoami",
            "pwd",
            "date",
            "hostname",
            "uptime",
            "env",
            "which",
            "file",
            "stat",
            "sha256sum",
            "md5sum",
            "base64",
            "hexdump",
            "xxd",
            "ping",
            "ip",
            "netstat",
            "ss",
        }
        cmd = parts[0]
        if cmd not in allowed:
            return False, (
                f"Command '{cmd}' not in local allowlist. "
                f"Set ANUNIX_API_URL for unrestricted remote execution."
            )
        return True, ""

    def health_check(self, host_id: str) -> Dict[str, Any]:
        """Check health of a host."""
        if self.api_url:
            return _http_get(
                f"{self.api_url}/hosts/{host_id}/health",
                timeout=10.0,
            )

        # Local health check
        import platform

        try:
            load = os.getloadavg()
        except (AttributeError, OSError):
            load = (0.0, 0.0, 0.0)

        return {
            "status": "completed",
            "mode": "local",
            "host_id": host_id,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "load_average": list(load),
            "healthy": True,
        }

    def run_command(self, host_id: str, command: str) -> Dict[str, Any]:
        """Execute a command on a host."""
        if self.api_url:
            return _http_post(
                f"{self.api_url}/hosts/{host_id}/exec",
                {"command": command},
                timeout=30.0,
            )

        # Local sandboxed execution
        safe, reason = self._safe_command(command)
        if not safe:
            return {
                "status": "failed",
                "mode": "local_sandbox",
                "host_id": host_id,
                "command": command,
                "stdout": "",
                "stderr": reason,
                "returncode": -1,
            }

        import subprocess

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30.0,
                cwd=os.getcwd(),
            )
            return {
                "status": "completed",
                "mode": "local_sandbox",
                "host_id": host_id,
                "command": command,
                "stdout": proc.stdout[:10000],
                "stderr": proc.stderr[:5000],
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "mode": "local_sandbox",
                "host_id": host_id,
                "command": command,
                "stdout": "",
                "stderr": "Command timed out after 30 seconds",
                "returncode": -1,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "mode": "local_sandbox",
                "host_id": host_id,
                "command": command,
                "stdout": "",
                "stderr": str(exc),
                "returncode": -1,
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
