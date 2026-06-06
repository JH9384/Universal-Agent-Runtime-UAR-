"""Encrypted credential vault for third-party service credentials.

Stores credentials encrypted at rest using Fernet (derived from SECRET_KEY).
Credentials are persisted in the run store's metadata layer so they work
across all store backends (JSON, SQLite, Postgres).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class CredentialEntry:
    """A single stored credential."""

    id: str
    name: str
    service_type: str  # e.g. 'ollama', 'autonomi', 'openai'
    encrypted_value: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_tested_at: Optional[float] = None
    last_test_status: Optional[str] = None  # 'ok' | 'error'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mask: bool = True) -> Dict[str, Any]:
        d = asdict(self)
        if mask:
            d["encrypted_value"] = "***"
        return d


class _StoreAdapter(Protocol):
    """Minimal interface the vault needs from a store."""

    def put_metadata(self, key: str, value: Any) -> None: ...

    def get_metadata(self, key: str) -> Any: ...

    def list_meta_keys(self) -> List[str]: ...


class CredentialVault:
    """Encrypted credential vault backed by store metadata."""

    _META_PREFIX = "uar:credential:"

    def __init__(self, store: _StoreAdapter):
        self._store = store
        self._fernet = self._init_fernet()

    def _init_fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            logger.warning(
                "cryptography not installed; credentials stored plaintext"
            )
            return None
        secret = os.getenv("SECRET_KEY", "")
        if not secret:
            logger.warning("SECRET_KEY not set; credentials stored plaintext")
            return None
        key = base64.urlsafe_b64encode(
            hashlib.sha256(secret.encode()).digest()[:32] + b"=" * 4
        )[:44]
        return Fernet(key)

    def _key(self, cred_id: str) -> str:
        return f"{self._META_PREFIX}{cred_id}"

    def _encrypt(self, plaintext: str) -> str:
        if self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        if self._fernet is None:
            return ciphertext
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def list_credentials(self) -> List[CredentialEntry]:
        """Return all stored credentials (values masked)."""
        creds: List[CredentialEntry] = []
        try:
            keys = self._store.list_meta_keys()
        except Exception:
            # Fallback: scan a reasonable range
            keys = [f"{self._META_PREFIX}{i}" for i in range(100)]
        for key in keys:
            if not key.startswith(self._META_PREFIX):
                continue
            try:
                raw = self._store.get_metadata(key)
                if not raw:
                    continue
                data = json.loads(raw) if isinstance(raw, str) else raw
                creds.append(CredentialEntry(**data))
            except Exception as exc:
                logger.debug("Skipping corrupt credential %s: %s", key, exc)
        return sorted(creds, key=lambda c: c.name)

    def get_credential(self, cred_id: str) -> Optional[CredentialEntry]:
        """Fetch a single credential by ID."""
        try:
            raw = self._store.get_metadata(self._key(cred_id))
            if not raw:
                return None
            data = json.loads(raw) if isinstance(raw, str) else raw
            return CredentialEntry(**data)
        except Exception as exc:
            logger.warning("Failed to get credential %s: %s", cred_id, exc)
            return None

    def get_decrypted(self, cred_id: str) -> Optional[str]:
        """Return the decrypted plaintext value for a credential."""
        cred = self.get_credential(cred_id)
        if cred is None:
            return None
        try:
            return self._decrypt(cred.encrypted_value)
        except Exception as exc:
            logger.error("Failed to decrypt credential %s: %s", cred_id, exc)
            return None

    def set_credential(
        self,
        cred_id: str,
        name: str,
        service_type: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CredentialEntry:
        """Store or update a credential."""
        existing = self.get_credential(cred_id)
        now = time.time()
        entry = CredentialEntry(
            id=cred_id,
            name=name,
            service_type=service_type,
            encrypted_value=self._encrypt(value),
            created_at=existing.created_at if existing else now,
            updated_at=now,
            last_tested_at=existing.last_tested_at if existing else None,
            last_test_status=existing.last_test_status if existing else None,
            metadata=metadata or existing.metadata if existing else {},
        )
        self._store.put_metadata(self._key(cred_id), json.dumps(asdict(entry)))
        logger.info("Stored credential %s (%s)", cred_id, service_type)
        return entry

    def delete_credential(self, cred_id: str) -> bool:
        """Remove a credential. Returns True if existed."""
        try:
            raw = self._store.get_metadata(self._key(cred_id))
            if raw:
                self._store.put_metadata(self._key(cred_id), "")
                return True
        except Exception as exc:
            logger.warning("Failed to delete credential %s: %s", cred_id, exc)
        return False

    def test_credential(self, cred_id: str) -> Dict[str, Any]:
        """Test connectivity for a credential.

        Returns a dict with 'ok' boolean and 'message' string.
        """
        cred = self.get_credential(cred_id)
        if cred is None:
            return {"ok": False, "message": "Credential not found"}

        decrypted = self.get_decrypted(cred_id)
        if decrypted is None:
            return {"ok": False, "message": "Failed to decrypt credential"}

        ok = False
        message = "Unsupported service type"

        if cred.service_type == "ollama":
            ok, message = self._test_ollama(decrypted)
        elif cred.service_type == "autonomi":
            ok, message = self._test_autonomi(decrypted)
        elif cred.service_type == "openai":
            ok, message = self._test_openai(decrypted)
        elif cred.service_type == "generic":
            ok, message = True, "Generic credential — manual test required"

        # Update test timestamp/status
        try:
            cred.last_tested_at = time.time()
            cred.last_test_status = "ok" if ok else "error"
            self._store.put_metadata(
                self._key(cred_id), json.dumps(asdict(cred))
            )
        except Exception as exc:
            logger.debug("Failed to update test status: %s", exc)

        return {"ok": ok, "message": message}

    def _test_ollama(self, host: str) -> tuple[bool, str]:
        import urllib.request

        try:
            req = urllib.request.Request(
                f"{host}/api/tags", method="GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200, "Ollama reachable"
        except Exception as exc:
            return False, f"Ollama unreachable: {exc}"

    def _test_autonomi(self, private_key: str) -> tuple[bool, str]:
        return (
            len(private_key) >= 32,
            "Key length OK (connectivity test not implemented)",
        )

    def _test_openai(self, api_key: str) -> tuple[bool, str]:
        import urllib.request

        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200, "OpenAI API reachable"
        except Exception as exc:
            return False, f"OpenAI unreachable: {exc}"


# Global singleton
_vault: Optional[CredentialVault] = None


def get_credential_vault(
    store: Optional[_StoreAdapter] = None,
) -> CredentialVault:
    """Return the global CredentialVault, lazily initialised."""
    global _vault
    if _vault is None:
        if store is None:
            from uar.container import get_container

            store = get_container().get_store()
        _vault = CredentialVault(store)
    return _vault
