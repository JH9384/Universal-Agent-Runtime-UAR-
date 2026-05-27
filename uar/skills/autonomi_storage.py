"""Autonomi decentralized storage integration skills.

Provides skills for storing and retrieving data on the Autonomi network:
  - autonomi_upload   : upload file/dir to Autonomi (public or private)
  - autonomi_download : download from an Autonomi address
  - autonomi_status   : check connectivity and wallet

Configure via env:
  AUTONOMI_PRIVATE_KEY    — EVM wallet private key (hex, with or without 0x prefix)
  AUTONOMI_NETWORK        — 'mainnet' or 'testnet' (default: testnet)
  AUTONOMI_TIMEOUT_SEC    — operation timeout in seconds (default: 300)

Goal metadata overrides:
  autonomi_private_key  — per-run wallet override
  autonomi_network      — per-run network override ('mainnet' or 'testnet')
  autonomi_public       — set True for public upload (default: False/private)
  autonomi_address      — address/data map for download
  autonomi_dest         — destination path for download
"""  # noqa: E501

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import cast

import re

from uar.core.async_utils import run_sync_safe
from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.validation import validate_path_security
from uar.core.exceptions import PathSecurityError

logger = logging.getLogger(__name__)

# Resolve allowed root from environment or use current working directory
_allowed_root_env = os.getenv("PROJECT_ROOT") or os.getenv("RUNS_DIR")
ALLOWED_ROOT = (
    Path(_allowed_root_env).resolve() if _allowed_root_env else Path.cwd()
)

_autonomi_cb = CircuitBreaker(
    "autonomi", failure_threshold=3, recovery_timeout=60.0
)


def _safe_filename(name: str) -> str:
    """Sanitize a string so it is safe to use as a filename."""
    safe = re.sub(r"[^\w.\-]+", "_", name)
    safe = safe.strip("._")
    if not safe:
        safe = "unnamed"
    return safe[:128]


def _get_autonomi():
    """Lazy import autonomi bindings. Returns None if not installed."""
    try:
        import autonomi

        return autonomi
    except ImportError:
        return None


def _resolve_input_path(ctx) -> Path | None:
    """Resolve upload source from metadata or prior doc_ingest step.

    Validates path security before returning.
    """
    raw = ctx.goal.metadata.get("input_path")
    if raw:
        p = Path(raw).resolve()
        try:
            validate_path_security(p, ALLOWED_ROOT)
            return p if p.exists() else None
        except Exception as e:
            logger.warning(f"Path security validation failed for {raw}: {e}")
            return None

    data = getattr(ctx, "data", None) or {}
    di = data.get("doc_ingest")
    if isinstance(di, dict) and di.get("documents"):
        for d in di["documents"]:
            if isinstance(d, dict):
                path_val = d.get("path")
                if path_val and isinstance(path_val, (str, bytes)):
                    resolved = cast(Path, Path(str(path_val)).resolve())
                    try:
                        validate_path_security(resolved, ALLOWED_ROOT)
                        if resolved.exists():
                            return resolved
                    except Exception as e:
                        logger.warning(
                            f"Path security validation failed for {path_val}: {e}"
                        )
                        continue
    return None


def _wallet_and_payment(autonomi_mod, private_key: str, network_name: str):
    """Create wallet and payment option from private key."""
    from autonomi import Wallet, Network, PaymentOption

    net = Network(network_name.lower() == "mainnet")
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    wallet = Wallet.new_from_private_key(net, private_key)
    payment = PaymentOption.wallet(wallet)
    return wallet, payment


# ---------------------------------------------------------------------------
# Skill: autonomi_upload
# ---------------------------------------------------------------------------


@register_skill("autonomi_upload")
def autonomi_upload(ctx):
    """Upload a file to Autonomi decentralized storage.

    Metadata:
      autonomi_source : file path to upload (required)
      autonomi_network : "testnet" or "mainnet" (default: testnet)
      autonomi_private_key : EVM wallet private key (optional, overrides env var)
    """  # noqa: E501
    mod = _get_autonomi()
    if mod is None:
        return {
            "status": "failed",
            "error": "autonomi Python package not installed. Run: pip install autonomi",  # noqa: E501
        }

    source = ctx.goal.metadata.get("autonomi_source")
    if not source:
        return {
            "status": "failed",
            "error": "Missing autonomi_source in metadata",
        }

    src = Path(source).resolve()
    try:
        validate_path_security(src, ALLOWED_ROOT)
    except Exception as e:
        logger.warning(f"Path security validation failed for {src}: {e}")
        return {"status": "failed", "error": f"Path security violation: {e}"}

    if not src.exists():
        return {"status": "failed", "error": f"Source not found: {src}"}

    if not src.is_file():
        raise ValueError(f"Path is neither file nor directory: {src}")

    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )
    public = bool(ctx.goal.metadata.get("autonomi_public", False))

    private_key = ctx.goal.metadata.get("autonomi_private_key") or os.getenv(
        "AUTONOMI_PRIVATE_KEY"
    )

    timeout = float(os.getenv("AUTONOMI_TIMEOUT_SEC", "300"))

    # Async upload ---------------------------------------------------------
    async def _do():
        from autonomi import Client

        client = await Client.init()
        if public:
            result = await client.file_upload_public(str(src))
        else:
            if not private_key:
                raise ValueError("Private key required for private uploads")
            _, payment = _wallet_and_payment(mod, private_key, network_name)
            result = await client.file_upload(str(src), payment)
        return result

    try:
        import asyncio
        result = _autonomi_cb.call(
            lambda: run_sync_safe(asyncio.wait_for(_do(), timeout=timeout))
        )
        return {
            "status": "completed",
            "address": str(result) if result else None,
            "public": public,
            "file_path": str(src),
            "network": network_name,
            "has_wallet": bool(private_key),
        }
    except (ValueError, TypeError, OSError) as exc:
        logger.exception("autonomi_upload failed")
        return {
            "status": "failed",
            "error": str(exc),
            "file_path": str(src),
            "network": network_name,
            "public": public,
        }


# ---------------------------------------------------------------------------
# Skill: autonomi_download
# ---------------------------------------------------------------------------


@register_skill("autonomi_download")
def autonomi_download(ctx):
    """Download a file from Autonomi by address or data map.

    Required metadata:
      autonomi_address  — the address/data map to download from

    Optional metadata:
      autonomi_public   — True for public data (default: False)
      autonomi_dest     — destination file path (default: .uar_library/downloads/<name>)

    Returns:
      {status, dest_path, address, public, network, error?}
    """  # noqa: E501
    mod = _get_autonomi()
    if mod is None:
        return {
            "status": "failed",
            "error": "autonomi Python package not installed. Run: pip install autonomi",  # noqa: E501
        }

    address = ctx.goal.metadata.get("autonomi_address")
    if not address:
        return {
            "status": "failed",
            "error": "No autonomi_address provided in metadata.",
        }

    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )
    public = bool(ctx.goal.metadata.get("autonomi_public", False))

    # Destination -----------------------------------------------------------
    dest_raw = ctx.goal.metadata.get("autonomi_dest")
    if not dest_raw:
        dest_raw = str(
            ALLOWED_ROOT
            / ".uar_library"
            / "downloads"
            / _safe_filename(str(address))
        )
    dest = Path(dest_raw).resolve()

    # Validate destination path security
    try:
        validate_path_security(dest, ALLOWED_ROOT)
    except (PathSecurityError, ValueError, OSError) as e:
        return {
            "status": "failed",
            "error": f"Destination path security violation: {e}",
            "address": address,
        }

    dest.parent.mkdir(parents=True, exist_ok=True)

    timeout = float(os.getenv("AUTONOMI_TIMEOUT_SEC", "300"))

    # Async download --------------------------------------------------------
    async def _do():
        from autonomi import Client

        client = await Client.init()
        if public:
            await client.file_download_public(address, str(dest))
        else:
            await client.file_download(address, str(dest))
        return str(dest)

    try:
        import asyncio
        _autonomi_cb.call(
            lambda: run_sync_safe(asyncio.wait_for(_do(), timeout=timeout))
        )
        return {
            "status": "completed",
            "dest_path": str(dest),
            "address": address,
            "public": public,
            "network": network_name,
        }
    except (ValueError, TypeError, OSError) as exc:
        logger.exception("autonomi_download failed")
        return {
            "status": "failed",
            "error": str(exc),
            "address": address,
            "network": network_name,
            "public": public,
        }


# ---------------------------------------------------------------------------
# Skill: autonomi_status
# ---------------------------------------------------------------------------


@register_skill("autonomi_status")
def autonomi_status(ctx):
    """Check Autonomi client availability and wallet status.

    Returns:
      {status, available, package_version, network, has_wallet, wallet_error?}
    """
    mod = _get_autonomi()
    if mod is None:
        return {
            "status": "failed",
            "available": False,
            "error": "autonomi Python package not installed",
        }

    private_key = ctx.goal.metadata.get("autonomi_private_key") or os.getenv(
        "AUTONOMI_PRIVATE_KEY"
    )
    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )

    result = {
        "status": "completed",
        "available": True,
        "package_version": getattr(mod, "__version__", "unknown"),
        "network": network_name,
        "has_wallet": bool(private_key),
    }

    if private_key:
        try:
            from autonomi import Wallet, Network

            net = Network(network_name.lower() == "mainnet")
            if private_key.startswith("0x"):
                private_key = private_key[2:]
            wallet = Wallet.new_from_private_key(net, private_key)
            # Expose wallet address if available
            result["wallet_address"] = str(
                getattr(wallet, "address", "unavailable")
            )
            # Redact private key from result
            result["has_wallet"] = True
        except Exception as exc:
            result["wallet_error"] = str(exc)
            result["has_wallet"] = False
    else:
        result["has_wallet"] = False

    return result
