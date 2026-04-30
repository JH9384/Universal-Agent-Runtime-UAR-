from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

PROOF_SCHEMA = "uar.schema.formal-proof.v1"
SIGNATURE_SCHEMA = "uar.schema.signature.v1"
DEFAULT_SIGNING_KEY_ID = os.getenv("UAR_SIGNING_KEY_ID", "local-dev-key")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def signing_secret() -> bytes:
    secret = os.getenv("UAR_SIGNING_SECRET") or "uar-local-development-signing-secret"
    return secret.encode("utf-8")


def sign_payload(payload: Any, key_id: str | None = None) -> dict[str, Any]:
    body = canonical_json(payload).encode("utf-8")
    signature = hmac.new(signing_secret(), body, hashlib.sha256).digest()
    return {
        "schema": SIGNATURE_SCHEMA,
        "algorithm": "HMAC-SHA256",
        "key_id": key_id or DEFAULT_SIGNING_KEY_ID,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signed_at": time.time(),
    }


def verify_signature(payload: Any, signature_record: dict[str, Any]) -> bool:
    expected = sign_payload(payload, signature_record.get("key_id"))["signature"]
    return hmac.compare_digest(expected, str(signature_record.get("signature", "")))


def build_formal_proof(*, subject_digest: str, claim: str, evidence: list[dict[str, Any]], proof_type: str = "integrity-lineage-proof", issuer: str = "uar.local") -> dict[str, Any]:
    proof_body = {
        "schema": PROOF_SCHEMA,
        "proof_type": proof_type,
        "issuer": issuer,
        "subject": subject_digest,
        "claim": claim,
        "evidence": evidence,
        "created_at": time.time(),
    }
    proof_body["proof_digest"] = sha256_digest(proof_body)
    proof_body["signature"] = sign_payload(proof_body)
    return proof_body
