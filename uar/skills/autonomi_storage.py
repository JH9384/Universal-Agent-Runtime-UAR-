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
import re
from pathlib import Path

from uar.core.async_utils import run_sync_safe
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.compat import lazy_import
from uar.core.exceptions import PathSecurityError
from uar.core.registry import register_skill
from uar.core.skill_utils import require_package, skill_guard
from uar.core.validation import validate_path_security

logger = logging.getLogger(__name__)

# Resolve allowed root from environment or use current working directory
_allowed_root_env = os.getenv("PROJECT_ROOT") or os.getenv("RUNS_DIR")
ALLOWED_ROOT = (
    Path(_allowed_root_env).resolve() if _allowed_root_env else Path.cwd()
)

_autonomi_cb = CircuitBreaker(
    "autonomi", failure_threshold=3, recovery_timeout=60.0
)


def _to_bool(value) -> bool:
    """Coerce a value to bool, handling string 'false'/'true' correctly."""
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "", "no", "off"}
    return bool(value)


def _safe_filename(name: str) -> str:
    """Sanitize a string so it is safe to use as a filename."""
    safe = re.sub(r"[^\w.\-]+", "_", name)
    safe = safe.strip("._")
    if not safe:
        safe = "unnamed"
    return safe[:128]


def _get_autonomi():
    """Lazy import autonomi bindings. Returns None if not installed."""
    return lazy_import("autonomi")


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
        except Exception:
            logger.warning(
                "Path security validation failed for %s", raw
            )
            return None

    data = getattr(ctx, "data", None) or {}
    di = data.get("doc_ingest")
    if isinstance(di, dict) and di.get("documents"):
        for d in di["documents"]:
            if isinstance(d, dict):
                path_val = d.get("path")
                if path_val and isinstance(path_val, str):
                    resolved = Path(path_val).resolve()
                    try:
                        validate_path_security(resolved, ALLOWED_ROOT)
                        if resolved.exists():
                            return resolved
                    except Exception:
                        logger.exception(
                            "Path security validation failed for %s", path_val
                        )
                        continue
    return None


def _wallet_and_payment(private_key: str, network_name: str):
    """Create wallet and payment option from private key."""
    from autonomi import Network, PaymentOption, Wallet

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
@skill_guard("Autonomi upload", status="failed")
def autonomi_upload(ctx):
    """Upload a file to Autonomi decentralized storage.

    Metadata:
      autonomi_source : file path to upload (required)
      autonomi_network : "testnet" or "mainnet" (default: testnet)
      autonomi_private_key : EVM wallet private key (optional, overrides env var)
    """  # noqa: E501
    err = require_package("autonomi")
    if err:
        return err

    source = ctx.goal.metadata.get("autonomi_source")
    if not source:
        return {
            "status": "failed",
            "error": "Missing autonomi_source in metadata",
        }

    src = Path(source).resolve()
    try:
        validate_path_security(src, ALLOWED_ROOT)
    except PathSecurityError:
        return {"status": "failed", "error": "Path security violation"}

    if not src.exists():
        return {"status": "failed", "error": "Source not found"}

    if not src.is_file() and not src.is_dir():
        return {"status": "failed", "error": "Path is not a file or directory"}

    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )
    public = _to_bool(ctx.goal.metadata.get("autonomi_public", False))

    private_key = ctx.goal.metadata.get("autonomi_private_key") or os.getenv(
        "AUTONOMI_PRIVATE_KEY"
    )

    timeout = max(
        1.0,
        float(
            os.getenv("AUTONOMI_TIMEOUT_SEC", "300").strip() or "300"
        ),
    )

    # Async upload ---------------------------------------------------------
    async def _do():
        from autonomi import Client

        client = await Client.init()
        if public:
            result = await client.file_upload_public(str(src))
        else:
            if not private_key:
                raise ValueError("Private key required for private uploads")
            _, payment = _wallet_and_payment(private_key, network_name)
            result = await client.file_upload(str(src), payment)
        return result

    import asyncio
    result = _autonomi_cb.call(
        lambda: run_sync_safe(asyncio.wait_for(_do(), timeout=timeout))
    )
    return {
        "status": "completed",
        "address": str(result) if result is not None else None,
        "public": public,
        "file_path": str(src),
        "network": network_name,
        "has_wallet": bool(private_key),
    }


# ---------------------------------------------------------------------------
# Skill: autonomi_download
# ---------------------------------------------------------------------------


@register_skill("autonomi_download")
@skill_guard("Autonomi download", status="failed")
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
    err = require_package("autonomi")
    if err:
        return err

    address = ctx.goal.metadata.get("autonomi_address")
    if not address:
        return {
            "status": "failed",
            "error": "No autonomi_address provided in metadata.",
        }

    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )
    public = _to_bool(ctx.goal.metadata.get("autonomi_public", False))

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
    except PathSecurityError:
        return {
            "status": "failed",
            "error": "Destination path security violation",
            "address": address,
        }

    dest.parent.mkdir(parents=True, exist_ok=True)

    timeout = max(
        1.0,
        float(
            os.getenv("AUTONOMI_TIMEOUT_SEC", "300").strip() or "300"
        ),
    )

    # Async download --------------------------------------------------------
    async def _do():
        from autonomi import Client

        client = await Client.init()
        if public:
            await client.file_download_public(address, str(dest))
        else:
            await client.file_download(address, str(dest))
        return str(dest)

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


# ---------------------------------------------------------------------------
# Skill: autonomi_status
# ---------------------------------------------------------------------------


@register_skill("autonomi_status")
@skill_guard("Autonomi status", status="failed")
def autonomi_status(ctx):
    """Check Autonomi client availability and wallet status.

    Returns:
      {status, available, package_version, network, has_wallet, wallet_error?}
    """
    err = require_package("autonomi")
    if err:
        err["available"] = False
        return err

    import autonomi as _autonomi_mod

    private_key = ctx.goal.metadata.get("autonomi_private_key") or os.getenv(
        "AUTONOMI_PRIVATE_KEY"
    )
    network_name = ctx.goal.metadata.get("autonomi_network") or os.getenv(
        "AUTONOMI_NETWORK", "testnet"
    )

    result = {
        "status": "completed",
        "available": True,
        "package_version": getattr(_autonomi_mod, "__version__", "unknown"),
        "network": network_name,
        "has_wallet": bool(private_key),
    }

    if private_key:
        try:
            from autonomi import Network, Wallet

            net = Network(network_name.lower() == "mainnet")
            if private_key.startswith("0x"):
                private_key = private_key[2:]
            wallet = Wallet.new_from_private_key(net, private_key)
            # Expose wallet address if available
            result["wallet_address"] = str(
                getattr(wallet, "address", "unavailable")
            )
            # Wallet validated successfully
            result["has_wallet"] = True
        except Exception:
            result["wallet_error"] = "Wallet check failed"
            result["has_wallet"] = False
    else:
        result["has_wallet"] = False

    return result
