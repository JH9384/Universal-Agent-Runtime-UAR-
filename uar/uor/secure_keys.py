"""Secure handling of cryptographic keys for UOR objects.

Provides secure storage, retrieval, and management of cryptographic keys
used for UOR object signing and verification.
"""

import logging
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KeyMetadata:
    """Metadata for a stored cryptographic key."""

    key_id: str
    key_type: str
    algorithm: str
    created_at: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key_id": self.key_id,
            "key_type": self.key_type,
            "algorithm": self.algorithm,
            "created_at": self.created_at,
            "description": self.description,
        }


class SecureKeyStore:
    """Secure key storage using environment variables."""

    def __init__(self, prefix: str = "UOR_KEY_"):
        """Initialize secure key store.

        Args:
            prefix: Environment variable prefix for keys
        """
        self.prefix = prefix

    def store_key(self, key_id: str, key_value: str) -> None:
        """Store a key in environment (for session only).

        WARNING: This stores in process environment only.
        For production, use a proper secrets manager.

        Args:
            key_id: Identifier for the key
            key_value: Key value to store
        """
        env_key = f"{self.prefix}{key_id.upper()}"
        os.environ[env_key] = key_value
        logger.info(f"Key stored in environment: {env_key}")

    def retrieve_key(self, key_id: str) -> Optional[str]:
        """Retrieve a key from environment.

        Args:
            key_id: Identifier for the key

        Returns:
            Key value if found, None otherwise
        """
        env_key = f"{self.prefix}{key_id.upper()}"
        value = os.environ.get(env_key)
        if value:
            logger.debug(f"Retrieved key from environment: {env_key}")
        return value

    def delete_key(self, key_id: str) -> bool:
        """Delete a key from environment.

        Args:
            key_id: Identifier for the key

        Returns:
            True if deleted, False if not found
        """
        env_key = f"{self.prefix}{key_id.upper()}"
        if env_key in os.environ:
            del os.environ[env_key]
            logger.info(f"Key deleted from environment: {env_key}")
            return True
        return False

    def list_keys(self) -> list[str]:
        """List all stored key IDs.

        Returns:
            List of key IDs
        """
        keys = []
        for key in os.environ:
            if key.startswith(self.prefix):
                key_id = key[len(self.prefix) :]
                keys.append(key_id.lower())
        return keys


class KeyManager:
    """Manager for cryptographic key operations."""

    def __init__(self, key_store: Optional[SecureKeyStore] = None):
        """Initialize key manager.

        Args:
            key_store: Key store instance
        """
        self.key_store = key_store or SecureKeyStore()

    def generate_key_pair(
        self, key_id: str, algorithm: str = "rsa", key_size: int = 2048
    ) -> KeyMetadata:
        """Generate a new key pair.

        Args:
            key_id: Identifier for the key
            algorithm: Key algorithm (rsa, ecdsa)
            key_size: Key size in bits

        Returns:
            KeyMetadata for the generated key

        Raises:
            NotImplementedError: If cryptography library not available
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            import datetime

            if algorithm == "rsa":
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size,
                    backend=default_backend(),
                )

                # Serialize private key
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode()

                # Store private key
                self.key_store.store_key(f"{key_id}_private", private_pem)

                # Get public key
                public_key = private_key.public_key()
                public_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode()

                # Store public key
                self.key_store.store_key(f"{key_id}_public", public_pem)

                metadata = KeyMetadata(
                    key_id=key_id,
                    key_type="rsa",
                    algorithm=f"rsa-{key_size}",
                    created_at=(
                        datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat()
                    ),
                    description=f"RSA {key_size}-bit key pair",
                )

                logger.info(f"Generated key pair: {key_id}")
                return metadata
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

        except ImportError:
            logger.error("cryptography library not available")
            raise NotImplementedError(
                "cryptography library required for key generation. "
                "Install with: pip install cryptography"
            )

    def sign_data(self, key_id: str, data: bytes) -> Optional[str]:
        """Sign data with a private key.

        Args:
            key_id: Identifier for the private key
            data: Data to sign

        Returns:
            Base64-encoded signature if successful, None otherwise
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key,
            )
            import base64

            private_key_pem = self.key_store.retrieve_key(f"{key_id}_private")
            if not private_key_pem:
                logger.error(f"Private key not found: {key_id}")
                return None

            private_key = load_pem_private_key(
                private_key_pem.encode(),
                password=None,
                backend=default_backend(),
            )

            signature = private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return base64.b64encode(signature).decode()

        except ImportError:
            logger.error("cryptography library not available")
            return None
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return None

    def verify_signature(
        self, key_id: str, data: bytes, signature: str
    ) -> bool:
        """Verify a signature with a public key.

        Args:
            key_id: Identifier for the public key
            data: Original data
            signature: Base64-encoded signature

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import (
                load_pem_public_key,
            )
            import base64

            public_key_pem = self.key_store.retrieve_key(f"{key_id}_public")
            if not public_key_pem:
                logger.error(f"Public key not found: {key_id}")
                return False

            public_key = load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend(),
            )

            signature_bytes = base64.b64decode(signature)

            try:
                public_key.verify(
                    signature_bytes,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
                return True
            except Exception:
                return False

        except ImportError:
            logger.error("cryptography library not available")
            return False
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
