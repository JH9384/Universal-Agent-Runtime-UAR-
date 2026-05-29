"""Cryptographic operations skill using PyCryptodome.

Provides encryption, decryption, hashing, and cryptographic operations
through PyCryptodome integration.

Environment Variables:
    CIPHER_TIMEOUT_SECONDS - Timeout for crypto operations (default: 30)
    CIPHER_MAX_DATA_SIZE - Max data size in bytes (default: 10485760)

Goal Metadata:
    cipher_operation - Operation: 'encrypt', 'decrypt', 'hash', 'sign', 'verify'
    cipher_algorithm - Algorithm: 'AES', 'SHA256', 'Ed25519'
    cipher_data - Data to process (base64 encoded string)
    cipher_key - Key for operations (base64 encoded)
    cipher_iv - IV for block ciphers (optional, base64 encoded)
"""  # noqa: E501

import os
import logging
import base64
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package, skill_guard

logger = logging.getLogger(__name__)

# Circuit breaker for crypto operations
_cipher_cb = CircuitBreaker(
    "cipher_ops", failure_threshold=3, recovery_timeout=30.0
)

# Configuration
CIPHER_TIMEOUT = max(
    1.0,
    float(
        os.getenv("CIPHER_TIMEOUT_SECONDS", "30").strip() or "30"
    ),
)
MAX_DATA_SIZE = max(
    1,
    int(
        os.getenv("CIPHER_MAX_DATA_SIZE", "10485760").strip()
        or "10485760"
    ),
)  # 10MB default


def _decode_base64(data: str) -> bytes:
    """Safely decode base64 data."""
    try:
        return base64.b64decode(data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid base64 data: {exc}") from exc


def _encode_base64(data: bytes) -> str:
    """Encode data to base64."""
    return base64.b64encode(data).decode("utf-8")


def _aes_encrypt(
    data: bytes, key: bytes, iv: bytes | None = None
) -> Dict[str, Any]:
    """Encrypt data using AES-CBC."""
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad

    if len(key) not in (16, 24, 32):
        return {
            "success": False,
            "error": (
                f"AES key must be 16, 24, or 32 bytes, got {len(key)}"
            ),
        }
    try:
        if iv is None:
            iv = get_random_bytes(16)
        elif len(iv) != 16:
            return {
                "success": False,
                "error": (
                    f"AES-CBC IV must be 16 bytes, got {len(iv)}"
                ),
            }
        cipher = AES.new(key, AES.MODE_CBC, iv)  # type: ignore
        padded_data = pad(data, AES.block_size)
        encrypted = cipher.encrypt(padded_data)

        return {
            "success": True,
            "encrypted_data": _encode_base64(encrypted),
            "iv": _encode_base64(iv),
            "algorithm": "AES-CBC",
        }
    except (ValueError, TypeError):
        logger.exception("AES encrypt failed")
        return {"success": False, "error": "Encryption failed"}


def _aes_decrypt(
    encrypted_data: bytes, key: bytes, iv: bytes
) -> Dict[str, Any]:
    """Decrypt data using AES-CBC."""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    if len(key) not in (16, 24, 32):
        return {
            "success": False,
            "error": (
                f"AES key must be 16, 24, or 32 bytes, got {len(key)}"
            ),
        }
    if len(iv) != 16:
        return {
            "success": False,
            "error": (
                f"AES-CBC IV must be 16 bytes, got {len(iv)}"
            ),
        }
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_data)
        unpadded = unpad(decrypted, AES.block_size)

        return {
            "success": True,
            "decrypted_data": _encode_base64(unpadded),
            "algorithm": "AES-CBC",
        }
    except (ValueError, TypeError):
        logger.exception("AES decrypt failed")
        return {"success": False, "error": "Decryption failed"}


def _hash_data(data: bytes, algorithm: str = "SHA256") -> Dict[str, Any]:
    """Hash data using specified algorithm."""
    from Crypto.Hash import SHA256, SHA512

    try:
        if algorithm == "SHA256":
            hasher = SHA256.new()  # type: ignore
        elif algorithm == "SHA512":
            hasher = SHA512.new()  # type: ignore
        else:
            return {
                "success": False,
                "error": "Unsupported algorithm",
            }

        hasher.update(data)
        digest = hasher.digest()

        return {
            "success": True,
            "hash": _encode_base64(digest),
            "algorithm": algorithm,
        }
    except (ValueError, TypeError):
        logger.exception("Hash failed")
        return {"success": False, "error": "Hash failed"}


def _sign_data(data: bytes, private_key: bytes) -> Dict[str, Any]:
    """Sign data using Ed25519."""
    from Crypto.Signature import ed25519  # type: ignore[attr-defined]

    try:
        key = ed25519.SigningKey(private_key)
        signature = key.sign(data)

        return {
            "success": True,
            "signature": _encode_base64(signature),
            "algorithm": "Ed25519",
        }
    except Exception:
        logger.exception("Sign failed")
        return {"success": False, "error": "Signing failed"}


def _verify_signature(
    data: bytes, signature: bytes, public_key: bytes
) -> Dict[str, Any]:
    """Verify signature using Ed25519."""
    from Crypto.Signature import ed25519  # type: ignore[attr-defined]

    try:
        key = ed25519.VerifyingKey(public_key)
        key.verify(signature, data)

        return {"success": True, "valid": True, "algorithm": "Ed25519"}
    except (ValueError, TypeError):
        return {
            "success": True,
            "valid": False,
            "error": "Signature verification failed",
            "algorithm": "Ed25519",
        }


@register_skill("cipher_ops")
@skill_guard("Cipher Ops", status="failed")
def cipher_ops(ctx: PipelineContext) -> Dict[str, Any]:
    """Perform cryptographic operations using PyCryptodome.

    Supports encryption, decryption, hashing, and digital signatures.
    Operations include AES encryption/decryption, SHA hashing,
    and Ed25519 signing/verification.

    Environment:
        CIPHER_TIMEOUT_SECONDS - Timeout for operations (default: 30)
        CIPHER_MAX_DATA_SIZE - Maximum data size in bytes (default: 10MB)

    Goal metadata:
        cipher_operation - Operation: 'encrypt', 'decrypt', 'hash', 'sign', 'verify'
        cipher_algorithm - Algorithm: 'AES', 'SHA256', 'Ed25519'
        cipher_data - Data to process (base64 encoded)
        cipher_key - Key for operations (base64 encoded)
        cipher_iv - IV for block ciphers (optional, base64 encoded)

    Returns:
        Dictionary with operation results or error information.
    """  # noqa: E501
    err = require_package("Crypto", install_hint="pip install pycryptodome")
    if err:
        return err

    # Get parameters from goal metadata
    operation = ctx.goal.metadata.get("cipher_operation", "hash")
    algorithm = ctx.goal.metadata.get("cipher_algorithm", "SHA256")
    data_b64 = ctx.goal.metadata.get("cipher_data", "")
    key_b64 = ctx.goal.metadata.get("cipher_key", "")
    iv_b64 = ctx.goal.metadata.get("cipher_iv", "")

    # Validate inputs
    if not data_b64:
        return {
            "status": "failed",
            "error": "cipher_data is required in goal metadata",
            "operation": operation,
        }

    try:
        data = _decode_base64(data_b64)
    except Exception:
        return {
            "status": "failed",
            "error": "Invalid cipher_data",
            "operation": operation,
        }

    if len(data) > MAX_DATA_SIZE:
        return {
            "status": "failed",
            "error": "Data too large",
            "operation": operation,
        }

    # Decode key if provided
    key = None
    if key_b64:
        try:
            key = _decode_base64(key_b64)
        except Exception:
            return {
                "status": "failed",
                "error": "Invalid cipher_key",
                "operation": operation,
            }

    # Decode IV if provided
    iv = None
    if iv_b64:
        try:
            iv = _decode_base64(iv_b64)
        except Exception:
            return {
                "status": "failed",
                "error": "Invalid cipher_iv",
                "operation": operation,
            }

    result = _cipher_cb.call(
        lambda: _execute_operation(operation, algorithm, data, key, iv)
    )

    # Add metadata to result
    result["operation"] = operation
    result["algorithm"] = algorithm
    result["status"] = "completed" if result.get("success") else "failed"

    return result


def _execute_operation(
    operation: str,
    algorithm: str,
    data: bytes,
    key: bytes | None,
    iv: bytes | None,
) -> Dict[str, Any]:
    """Execute the specified cryptographic operation."""
    operations = {
        "encrypt": lambda: _aes_encrypt(data, key or b"", iv),
        "decrypt": lambda: _aes_decrypt(data, key or b"", iv or b""),
        "hash": lambda: _hash_data(data, algorithm),
        "sign": lambda: _sign_data(data, key or b""),
        "verify": lambda: _verify_signature(data, key or b"", iv or b""),
    }

    if operation not in operations:
        return {
            "success": False,
            "error": (
                f"Unknown operation: {operation}. "
                f"Available: {list(operations.keys())}"
            ),
        }

    return operations[operation]()


@register_skill("crypto_analyze")
@skill_guard("Crypto Analyze")
def crypto_analyze(ctx: PipelineContext) -> Dict[str, Any]:
    """Cryptographic analysis: hash identification, entropy, key strength.

    Metadata:
        analyze_data:     base64-encoded data to analyze
        analyze_type:       'hash_id', 'entropy', 'key_strength',
                            'frequency', 'all' (default)
    """
    err = require_package("Crypto", install_hint="pip install pycryptodome")
    if err:
        return err

    import math
    from collections import Counter

    meta = ctx.goal.metadata or {}
    data_b64 = meta.get("analyze_data", "")
    analyze_type = meta.get("analyze_type", "all")

    if not data_b64:
        return {"status": "failed", "error": "analyze_data required"}

    try:
        data = _decode_base64(data_b64)
    except Exception:
        return {"status": "failed", "error": "Invalid base64 data"}

    results: Dict[str, Any] = {}

    # Entropy (Shannon)
    if analyze_type in ("entropy", "all"):
        if data:
            counter = Counter(data)
            length = len(data)
            entropy = -sum(
                (count / length) * math.log2(count / length)
                for count in counter.values()
            )
            results["entropy"] = round(entropy, 4)
            results["entropy_bits_per_byte"] = round(entropy, 4)
            results["is_random_like"] = entropy > 7.5
        else:
            results["entropy"] = 0.0

    # Hash identification
    if analyze_type in ("hash_id", "all"):
        hex_preview = data[:32].hex()
        hash_types = []
        if len(data) == 16:
            hash_types.append("MD5")
        if len(data) == 20:
            hash_types.append("SHA1")
        if len(data) == 32:
            hash_types.append("SHA256")
        if len(data) == 48:
            hash_types.append("SHA384")
        if len(data) == 64:
            hash_types.append("SHA512")
        results["hash_length"] = len(data)
        results["possible_hash_types"] = hash_types
        results["hex_preview"] = hex_preview

    # Frequency analysis
    if analyze_type in ("frequency", "all"):
        if data:
            counter = Counter(data)
            total = len(data)
            freq = {
                hex(b): round(count / total, 4)
                for b, count in counter.most_common(10)
            }
            results["top_bytes"] = freq
        else:
            results["top_bytes"] = {}

    # Key strength (if data is interpreted as a key)
    if analyze_type in ("key_strength", "all"):
        key_len = len(data) * 8
        strength = (
            "weak" if key_len < 128 else "good" if key_len < 256 else "strong"
        )
        results["key_bits"] = key_len
        results["key_strength"] = strength

    return {"status": "completed", "analysis": results}
