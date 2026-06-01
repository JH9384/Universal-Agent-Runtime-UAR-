"""Unit tests for Replay Explorer (T6).

Tests the `replay_explorer` router endpoint via FastAPI TestClient.
"""

import time

import pytest
from fastapi.testclient import TestClient

import uar.api.middleware as _mw
from uar.core.contracts import RunRecord
from uar.memory.sqlite_store import SqliteRunStore

_TEST_KEY = "test-key-explorer-001"
_TEST_HEADERS = {"Authorization": f"Bearer {_TEST_KEY}"}


def _make_events(run_id: str) -> list:
    return [
        {
            "schema_version": "uar.event.v1",
            "type": "start",
            "run_id": run_id,
            "goal_id": "g1",
            "skill": None,
            "timestamp": time.time(),
            "payload": {"skills": ["echo"]},
            "error": None,
        },
        {
            "schema_version": "uar.event.v1",
            "type": "complete",
            "run_id": run_id,
            "goal_id": "g1",
            "skill": None,
            "timestamp": time.time() + 0.1,
            "payload": {
                "status": "success",
                "outputs": ["ok"],
                "errors": [],
                "final_context": {},
            },
            "error": None,
        },
    ]


@pytest.fixture(autouse=True)
def _inject_api_key(monkeypatch):
    monkeypatch.setitem(
        _mw.API_KEYS, _TEST_KEY, {"user": "test", "tier": "admin"}
    )


@pytest.fixture()
def stored_run(tmp_path, monkeypatch):
    """Store a run record and return (store, run_id)."""
    import uar.api.server as _server_mod

    store = SqliteRunStore(path=str(tmp_path / "explorer2.db"))
    monkeypatch.setattr(_server_mod, "store", store)

    run_id = f"explorer-run-{int(time.time() * 1000)}"
    record = RunRecord(
        run_id=run_id,
        goal_id="g1",
        skills=["echo"],
        status="success",
        outputs=["ok"],
        events=_make_events(run_id),
        final_context={"x": 1},
    )
    store.append(record)
    return store, run_id


def test_explorer_bundle_has_required_keys(stored_run):
    store, run_id = stored_run
    from uar.api.server import app
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer", headers=_TEST_HEADERS
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_id"] == run_id
    assert "summary" in data
    assert "timeline" in data
    assert "confidence" in data
    assert "failure_path" in data
    assert "events" in data


def test_explorer_404_for_missing_run():
    from uar.api.server import app
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        "/api/uar/runs/nonexistent-run-xyz/explorer",
        headers=_TEST_HEADERS,
    )
    assert resp.status_code == 404


def test_explorer_summary_fields(stored_run):
    store, run_id = stored_run
    from uar.api.server import app
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer", headers=_TEST_HEADERS
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()["summary"]
    assert summary["run_id"] == run_id
    assert "status" in summary
    assert "skills" in summary


def test_explorer_events_match_stored_count(stored_run):
    store, run_id = stored_run
    from uar.api.server import app
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer", headers=_TEST_HEADERS
    )
    assert resp.status_code == 200, resp.text
    events = resp.json()["events"]
    assert len(events) == 2
