"""Cryptographic custody for Semantic Replay history corpora."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)

ATTESTATION_SCHEMA = "uar.semantic-history-attestation.v1"


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON representation used by the attestation."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def build_history_attestation_manifest(
    payload: Mapping[str, Any],
    *,
    key_id: str,
    review_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the complete census a trusted collector must sign."""

    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {}
    sanitization = provenance.get("sanitization")
    if not isinstance(sanitization, Mapping):
        sanitization = {}
    runs = payload.get("runs")
    if not isinstance(runs, list):
        runs = []
    census = []
    for run in runs:
        if not isinstance(run, Mapping):
            census.append({"invalid_run_sha256": _sha256(run)})
            continue
        census.append(
            {
                "run_id": run.get("run_id"),
                "pair_id": run.get("pair_id"),
                "split": run.get("split"),
                "cohort": run.get("cohort"),
                "task_class": run.get("task_class"),
                "final_result_class": run.get("final_result_class"),
                "event_mode": run.get("event_mode"),
                "case_id": run.get("case_id"),
                "seed": run.get("seed"),
                "runtime_projection_hash": run.get("runtime_projection_hash"),
                "event_stream_sha256": _sha256(run.get("events")),
            }
        )
    corpus = {
        "schema": payload.get("schema"),
        "provenance": provenance,
        "runs": runs,
    }
    return {
        "schema": ATTESTATION_SCHEMA,
        "key_id": key_id,
        "corpus_schema": payload.get("schema"),
        "source_snapshot": sanitization.get("source_snapshot"),
        "code_revision": provenance.get("code_revision"),
        "capture_window": provenance.get("capture_window"),
        "review_policy_sha256": _sha256(review_policy),
        "corpus_sha256": _sha256(corpus),
        "run_count": len(runs),
        "census": census,
    }


def verify_history_attestation(
    payload: Mapping[str, Any],
    *,
    review_policy: Mapping[str, Any],
    trusted_public_keys: Mapping[str, bytes],
) -> tuple[bool, tuple[str, ...]]:
    """Verify corpus custody against caller-supplied Ed25519 trust anchors."""

    attestation = payload.get("attestation")
    if not isinstance(attestation, Mapping):
        return False, ("missing_signed_attestation",)
    manifest = attestation.get("manifest")
    signature = attestation.get("signature")
    if not isinstance(manifest, Mapping) or not isinstance(signature, str):
        return False, ("malformed_signed_attestation",)
    key_id = manifest.get("key_id")
    if not isinstance(key_id, str) or not key_id:
        return False, ("missing_attestation_key_id",)
    expected = build_history_attestation_manifest(
        payload,
        key_id=key_id,
        review_policy=review_policy,
    )
    if dict(manifest) != expected:
        return False, ("attestation_manifest_mismatch",)
    public_key_pem = trusted_public_keys.get(key_id)
    if public_key_pem is None:
        return False, ("untrusted_attestation_key",)
    try:
        public_key = load_pem_public_key(public_key_pem)
        if not isinstance(public_key, Ed25519PublicKey):
            return False, ("invalid_attestation_key_type",)
        signature_bytes = base64.b64decode(signature, validate=True)
        public_key.verify(signature_bytes, canonical_json_bytes(manifest))
    except (
        AttributeError,
        binascii.Error,
        InvalidSignature,
        TypeError,
        UnsupportedAlgorithm,
        ValueError,
    ):
        return False, ("invalid_attestation_signature",)
    return True, ()


def sign_history_attestation(
    payload: Mapping[str, Any],
    *,
    key_id: str,
    review_policy: Mapping[str, Any],
    private_key_pem: bytes,
) -> dict[str, Any]:
    """Build and sign a corpus census with an Ed25519 private key."""

    private_key = load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("invalid_attestation_private_key_type")
    manifest = build_history_attestation_manifest(
        payload,
        key_id=key_id,
        review_policy=review_policy,
    )
    signature = base64.b64encode(
        private_key.sign(canonical_json_bytes(manifest))
    ).decode("ascii")
    return {"manifest": manifest, "signature": signature}


__all__ = [
    "ATTESTATION_SCHEMA",
    "build_history_attestation_manifest",
    "canonical_json_bytes",
    "sign_history_attestation",
    "verify_history_attestation",
]
