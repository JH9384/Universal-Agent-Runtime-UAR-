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
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from uar.core.registry import register_skill

logger = logging.getLogger(__name__)


def _get_autonomi():
    """Lazy import autonomi bindings. Returns None if not installed."""
    try:
        import autonomi
        return autonomi
    except ImportError:
        return None


def _resolve_input_path(ctx) -> Path | None:
    """Resolve upload source from metadata or prior doc_ingest step."""
    raw = ctx.goal.metadata.get("input_path")
    if raw:
        p = Path(raw).resolve()
        return p if p.exists() else None

    data = getattr(ctx, "data", None) or {}
    di = data.get("doc_ingest")
    if isinstance(di, dict) and di.get("documents"):
        for d in di["documents"]:
            if isinstance(d, dict):
                p = d.get("path")
                if p:
                    resolved = Path(p).resolve()
                    if resolved.exists():
                        return resolved
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
    """Upload a file or directory to the Autonomi decentralized network.

    Source resolution order:
      1. input_path from goal metadata
      2. First existing file path from prior doc_ingest documents

    Returns:
      {status, address, public, file_path, network, error?}
    """
    mod = _get_autonomi()
    if mod is None:
        return {
            "status": "failed",
            "error": "autonomi Python package not installed. Run: pip install autonomi",
        }

    src = _resolve_input_path(ctx)
    if not src:
        return {
            "status": "failed",
            "error": (
                "No input_path provided and no documents found from prior steps. "
                "Upload requires a file or directory source."
            ),
        }

    # Configuration ----------------------------------------------------------
    private_key = (
        ctx.goal.metadata.get("autonomi_private_key")
        or os.getenv("AUTONOMI_PRIVATE_KEY")
    )
    network_name = (
        ctx.goal.metadata.get("autonomi_network")
        or os.getenv("AUTONOMI_NETWORK", "testnet")
    )
    public = bool(ctx.goal.metadata.get("autonomi_public", False))
    timeout = float(os.getenv("AUTONOMI_TIMEOUT_SEC", "300"))

    if not private_key:
        return {
            "status": "failed",
            "error": (
                "No Autonomi private key configured. Set AUTONOMI_PRIVATE_KEY env var "
                "or pass autonomi_private_key in metadata."
            ),
        }

    # Async upload -----------------------------------------------------------
    async def _do():
        from autonomi import Client
        _, payment = _wallet_and_payment(mod, private_key, network_name)
        client = await Client.init()

        if src.is_file():
            if public:
                result = await client.file_content_upload_public(str(src), payment)
            else:
                result = await client.file_content_upload(str(src), payment)
        elif src.is_dir():
            if public:
                result = await client.dir_content_upload_public(str(src), payment)
            else:
                result = await client.dir_content_upload(str(src), payment)
        else:
            raise ValueError(f"Path is neither file nor directory: {src}")
        return result

    try:
        result = asyncio.run(asyncio.wait_for(_do(), timeout=timeout))
        return {
            "status": "completed",
            "address": str(result) if result else None,
            "public": public,
            "file_path": str(src),
            "network": network_name,
        }
    except Exception as exc:
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
    """
    mod = _get_autonomi()
    if mod is None:
        return {
            "status": "failed",
            "error": "autonomi Python package not installed. Run: pip install autonomi",
        }

    address = ctx.goal.metadata.get("autonomi_address")
    if not address:
        return {
            "status": "failed",
            "error": "No autonomi_address provided in metadata.",
        }

    network_name = (
        ctx.goal.metadata.get("autonomi_network")
        or os.getenv("AUTONOMI_NETWORK", "testnet")
    )
    public = bool(ctx.goal.metadata.get("autonomi_public", False))

    # Destination -----------------------------------------------------------
    dest_raw = ctx.goal.metadata.get("autonomi_dest")
    if not dest_raw:
        root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        dest_raw = str(root / ".uar_library" / "downloads" / Path(str(address)).name)
    dest = Path(dest_raw).resolve()
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
        asyncio.run(asyncio.wait_for(_do(), timeout=timeout))
        return {
            "status": "completed",
            "dest_path": str(dest),
            "address": address,
            "public": public,
            "network": network_name,
        }
    except Exception as exc:
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

    private_key = (
        ctx.goal.metadata.get("autonomi_private_key")
        or os.getenv("AUTONOMI_PRIVATE_KEY")
    )
    network_name = (
        ctx.goal.metadata.get("autonomi_network")
        or os.getenv("AUTONOMI_NETWORK", "testnet")
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
            result["wallet_address"] = str(getattr(wallet, "address", "unavailable"))
        except Exception as exc:
            result["wallet_error"] = str(exc)

    return result
