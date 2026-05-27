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


def _check_pycryptodome_available() -> bool:
    """Check if PyCryptodome is available with graceful degradation."""
    import importlib.util

    return importlib.util.find_spec("Crypto") is not None


def _decode_base64(data: str) -> bytes:
    """Safely decode base64 data."""
    try:
        return base64.b64decode(data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid base64 data: {exc}")


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
    except (ValueError, TypeError) as exc:
        logger.warning(f"AES encrypt failed: {exc}")
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
    except (ValueError, TypeError) as exc:
        logger.warning(f"AES decrypt failed: {exc}")
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
    except (ValueError, TypeError) as exc:
        logger.warning(f"Hash failed: {exc}")
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
    except Exception as exc:
        logger.warning(f"Sign failed: {exc}")
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
    # Check PyCryptodome availability
    if not _check_pycryptodome_available():
        return {
            "status": "failed",
            "error": "PyCryptodome not installed. Install with: pip install pycryptodome",  # noqa: E501
            "operation": "unavailable",
        }

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

    # Execute operation with circuit breaker
    try:
        result = _cipher_cb.call(
            lambda: _execute_operation(operation, algorithm, data, key, iv)
        )
    except Exception as exc:
        logger.warning(f"cipher_ops failed: {exc}")
        return {
            "status": "failed",
            "error": "Operation failed",
            "operation": operation,
        }

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
