"""Canonical UOR address helpers backed by the `uor-addr` reference impl."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

try:  # Prefer canonical reference implementation
    from uor_addr import AddressError, kappa  # type: ignore

    _HAS_NATIVE = True
except ImportError:  # Fallback to pure-Python JCS + SHA-256
    _HAS_NATIVE = False
    from rfc8785 import dumps as rfc8785_dumps  # type: ignore[attr-defined]


class UORAddressError(RuntimeError):
    """Raised when canonical address derivation fails."""


def _to_json_bytes(value: Dict[str, Any]) -> bytes:
    try:
        return json.dumps(value, separators=(",", ":")).encode("utf-8")
    except TypeError as exc:  # non-serializable payload
        raise UORAddressError("Value is not JSON serializable") from exc


def _address_via_rfc8785(data: bytes) -> str:
    try:
        canonical = rfc8785_dumps(json.loads(data.decode("utf-8")))
    except Exception as exc:  # pragma: no cover - library handles types
        raise UORAddressError("Failed to canonicalize JSON") from exc
    canonical_bytes = (
        canonical
        if isinstance(canonical, bytes)
        else canonical.encode("utf-8")
    )
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"


def _address_via_native(data: bytes) -> str:
    try:
        return kappa.json_address(data)
    except AddressError as exc:
        raise UORAddressError(str(exc)) from exc


def address_for_json(value: Dict[str, Any]) -> str:
    """Return the canonical `uor://`-style label for a JSON document."""
    data = _to_json_bytes(value)
    if _HAS_NATIVE:
        return _address_via_native(data)
    return _address_via_rfc8785(data)


def address_with_witness(
    value: Dict[str, Any]
) -> tuple[str, Dict[str, Any] | None]:
    """Return address and witness payload (if native bindings available)."""
    data = _to_json_bytes(value)
    if _HAS_NATIVE and hasattr(kappa, "json_address_with_witness"):
        try:
            with kappa.json_address_with_witness(data) as grounded:
                label = grounded.kappa_label()
                witness_payload = {
                    "fingerprint": grounded.content_fingerprint().hex(),
                    "verified_label": grounded.verify(),
                }
                return label, witness_payload
        except AddressError as exc:
            raise UORAddressError(str(exc)) from exc
    return _address_via_rfc8785(data), None
