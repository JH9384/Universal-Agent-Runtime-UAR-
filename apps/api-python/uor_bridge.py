from __future__ import annotations

import os
from typing import Any

import requests

UOR_API_BASE = os.getenv("UOR_API_BASE", "https://api.uor.foundation/v1")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("UOR_BRIDGE_TIMEOUT_SECONDS", "10"))


class UORBridgeError(RuntimeError):
    pass


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{UOR_API_BASE.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.get(url, params=params or {}, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise UORBridgeError(f"UOR bridge request failed: {url}: {exc}") from exc


def navigate() -> dict[str, Any]:
    return _get("/navigate")


def kernel_verify(x: int = 42) -> dict[str, Any]:
    return _get("/kernel/op/verify", {"x": x})


def bridge_trace(x: int = 42, ops: str = "neg,bnot") -> dict[str, Any]:
    return _get("/bridge/trace", {"x": x, "ops": ops})


def conformance_probe() -> dict[str, Any]:
    verify = kernel_verify(42)
    trace = bridge_trace(42, "neg,bnot")
    verified = bool(
        verify.get("proof:verified")
        or verify.get("verified")
        or verify.get("proof", {}).get("verified")
    )
    return {
        "api_base": UOR_API_BASE,
        "verify_42": verify,
        "trace_42_neg_bnot": trace,
        "critical_identity_verified": verified,
    }
