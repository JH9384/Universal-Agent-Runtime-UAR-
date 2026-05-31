"""Tests for secure key storage and management.

Covers KeyMetadata, SecureKeyStore, and KeyManager.
"""

import importlib.util
import os

import pytest

from uar.uor.secure_keys import KeyMetadata, SecureKeyStore, KeyManager


CRYPTO_AVAILABLE = importlib.util.find_spec("cryptography") is not None


class TestKeyMetadata:
    """KeyMetadata dataclass."""

    def test_to_dict(self):
        m = KeyMetadata(
            key_id="k1", key_type="rsa", algorithm="rsa-2048",
            created_at="2024-01-01", description="test key",
        )
        d = m.to_dict()
        assert d["key_id"] == "k1"
        assert d["algorithm"] == "rsa-2048"
        assert d["description"] == "test key"


class TestSecureKeyStore:
    """Secure key storage."""

    def test_store_and_retrieve(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        store.store_key("secret", "my-value")
        assert store.retrieve_key("secret") == "my-value"
        assert os.environ["TEST_KEY_SECRET"] == "my-value"
        store.delete_key("secret")

    def test_retrieve_missing(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        assert store.retrieve_key("nonexistent") is None

    def test_delete_existing(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        store.store_key("tmp", "val")
        assert store.delete_key("tmp") is True
        assert store.retrieve_key("tmp") is None

    def test_delete_missing(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        assert store.delete_key("nonexistent") is False

    def test_list_keys(self):
        store = SecureKeyStore(prefix="TEST_KEY_")
        store.store_key("a", "1")
        store.store_key("b", "2")
        keys = store.list_keys()
        assert "a" in keys
        assert "b" in keys
        store.delete_key("a")
        store.delete_key("b")

    def test_custom_prefix(self):
        store = SecureKeyStore(prefix="CUSTOM_")
        store.store_key("x", "y")
        assert os.environ["CUSTOM_X"] == "y"
        store.delete_key("x")


class TestKeyManagerInit:
    """KeyManager initialization."""

    def test_default_store(self):
        mgr = KeyManager()
        assert mgr.key_store is not None

    def test_custom_store(self):
        store = SecureKeyStore()
        mgr = KeyManager(key_store=store)
        assert mgr.key_store is store


class TestKeyManagerGenerate:
    """Key generation with cryptography."""

    @pytest.mark.skipif(
        not CRYPTO_AVAILABLE, reason="cryptography not installed"
    )
    def test_generate_rsa(self):
        store = SecureKeyStore(prefix="TEST_KM_")
        mgr = KeyManager(key_store=store)
        meta = mgr.generate_key_pair(
            "test_rsa", algorithm="rsa", key_size=1024
        )
        assert meta.key_id == "test_rsa"
        assert meta.key_type == "rsa"
        assert "rsa-1024" in meta.algorithm
        # Keys stored
        assert store.retrieve_key("test_rsa_private") is not None
        assert store.retrieve_key("test_rsa_public") is not None
        store.delete_key("test_rsa_private")
        store.delete_key("test_rsa_public")

    @pytest.mark.skipif(
        not CRYPTO_AVAILABLE, reason="cryptography not installed"
    )
    def test_unsupported_algorithm(self):
        store = SecureKeyStore(prefix="TEST_KM_")
        mgr = KeyManager(key_store=store)
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            mgr.generate_key_pair("test", algorithm="ecdsa")

    def test_sign_exception(self):
        store = SecureKeyStore(prefix="TEST_KM_")
        store.store_key("bad_private", "not-a-valid-key")
        mgr = KeyManager(key_store=store)
        assert mgr.sign_data("bad", b"data") is None

    def test_verify_exception(self):
        store = SecureKeyStore(prefix="TEST_KM_")
        store.store_key("bad_public", "not-a-valid-key")
        mgr = KeyManager(key_store=store)
        assert mgr.verify_signature("bad", b"data", "sig") is False


class TestSignVerify:
    """Signing and verification roundtrip."""

    @pytest.mark.skipif(
        not CRYPTO_AVAILABLE, reason="cryptography not installed"
    )
    def test_sign_and_verify(self):
        store = SecureKeyStore(prefix="TEST_SV_")
        mgr = KeyManager(key_store=store)
        mgr.generate_key_pair("sign_test", algorithm="rsa", key_size=1024)
        data = b"hello world"
        sig = mgr.sign_data("sign_test", data)
        assert sig is not None
        assert mgr.verify_signature("sign_test", data, sig) is True
        store.delete_key("sign_test_private")
        store.delete_key("sign_test_public")

    @pytest.mark.skipif(
        not CRYPTO_AVAILABLE, reason="cryptography not installed"
    )
    def test_verify_bad_signature(self):
        store = SecureKeyStore(prefix="TEST_SV_")
        mgr = KeyManager(key_store=store)
        mgr.generate_key_pair("verify_test", algorithm="rsa", key_size=1024)
        data = b"hello world"
        assert mgr.verify_signature("verify_test", data, "bad_sig") is False
        store.delete_key("verify_test_private")
        store.delete_key("verify_test_public")

    @pytest.mark.skipif(
        not CRYPTO_AVAILABLE, reason="cryptography not installed"
    )
    def test_verify_wrong_data(self):
        store = SecureKeyStore(prefix="TEST_SV_")
        mgr = KeyManager(key_store=store)
        mgr.generate_key_pair("wrong_data", algorithm="rsa", key_size=1024)
        sig = mgr.sign_data("wrong_data", b"original")
        assert sig is not None
        assert mgr.verify_signature("wrong_data", b"tampered", sig) is False
        store.delete_key("wrong_data_private")
        store.delete_key("wrong_data_public")

    def test_sign_missing_key(self):
        store = SecureKeyStore(prefix="TEST_SV_")
        mgr = KeyManager(key_store=store)
        assert mgr.sign_data("missing", b"data") is None

    def test_verify_missing_key(self):
        store = SecureKeyStore(prefix="TEST_SV_")
        mgr = KeyManager(key_store=store)
        assert mgr.verify_signature("missing", b"data", "sig") is False
