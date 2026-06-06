"""Tests for T12 — GDPR Compliance.

Covers:
- GDPRController export, erase, policy
- Privacy API endpoints
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from uar.api.server import app
from uar.core.gdpr import GDPRController

client = TestClient(app)


@pytest.fixture
def api_keys():
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "admin"}},
        clear=True,
    ):
        yield


class FakeStore:
    """Minimal fake store for GDPR unit tests."""

    def __init__(self, records=None, meta=None):
        self._records = records or []
        self._meta = meta or {}

    def list_records(self, user_id=None, limit=1000):
        return [
            r for r in self._records
            if r.get("user_id") == user_id
        ][:limit]

    def list_meta_keys(self):
        return list(self._meta.keys())

    def get_metadata(self, key):
        return self._meta.get(key)

    def delete(self, run_id):
        self._records = [
            r for r in self._records
            if r.get("run_id") != run_id
        ]
        return True


def test_controller_policy():
    ctrl = GDPRController(FakeStore())
    policy = ctrl.policy_metadata()
    assert policy["data_controller"] == "UAR Operator"
    assert "rights" in policy
    assert "erasure" in policy["rights"]


def test_controller_export():
    store = FakeStore(
        records=[
            {"run_id": "r1", "user_id": "alice", "skills": []},
            {"run_id": "r2", "user_id": "alice", "skills": []},
            {"run_id": "r3", "user_id": "bob", "skills": []},
        ],
        meta={"k": "v"},
    )
    ctrl = GDPRController(store)
    data = ctrl.export_data("alice")
    assert data["user_id"] == "alice"
    assert data["record_count"] == 2


def test_controller_erase():
    store = FakeStore(
        records=[
            {"run_id": "r1", "user_id": "alice", "skills": []},
            {"run_id": "r2", "user_id": "alice", "skills": []},
            {"run_id": "r3", "user_id": "bob", "skills": []},
        ],
    )
    ctrl = GDPRController(store)
    removed = ctrl.erase_data("alice")
    assert removed == 2
    assert len(store.list_records(user_id="alice")) == 0
    assert len(store.list_records(user_id="bob")) == 1


class TestPrivacyEndpoints:
    def test_policy_no_auth(self):
        """Policy endpoint is open."""
        resp = client.get("/api/uar/privacy/policy")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["data_controller"] == "UAR Operator"

    @pytest.mark.usefixtures("api_keys")
    def test_export_requires_auth(self, api_keys):
        resp = client.get("/api/uar/privacy/export")
        assert resp.status_code == 401

    @pytest.mark.usefixtures("api_keys")
    def test_erase_requires_auth(self, api_keys):
        resp = client.delete("/api/uar/privacy/erase")
        assert resp.status_code == 401
