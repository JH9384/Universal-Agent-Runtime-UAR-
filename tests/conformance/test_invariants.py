"""UOR conformance invariants for the consolidated UAR application.

These tests exercise the object/runtime/agent endpoints exposed by
:mod:`uar.api.routers.uor` and back the UOR Foundation conformance
contract. The test fixture overrides the FastAPI dependency to inject
a fresh per-test :class:`uar.objects.store.ObjectStore` backed by a
temporary SQLite file.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from uar.api.routers.uor import get_store
from uar.api.server import app
from uar.objects import ObjectStore, seed_standard_runtimes

CI_STABLE_TIMEOUT = 10.0


@pytest.fixture()
def uor(tmp_path):
    """Provide an isolated ``(store, client)`` pair per test."""
    store = ObjectStore(db_path=str(tmp_path / "uor-test.sqlite3"))
    seed_standard_runtimes(store)
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield store, client
    finally:
        app.dependency_overrides.pop(get_store, None)


def create_object(
    client: TestClient, content: Any, attributes=None
) -> Dict[str, Any]:
    response = client.post(
        "/objects",
        json={"content": content, "attributes": attributes or {}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_digest_is_deterministic_for_same_payload(uor):
    _, client = uor
    a = create_object(client, {"x": 1, "y": [2, 3]}, {"type": "demo"})
    b = create_object(client, {"x": 1, "y": [2, 3]}, {"type": "demo"})
    assert a["digest"] == b["digest"]


def test_object_roundtrip_and_verify(uor):
    _, client = uor
    obj = create_object(client, 42)

    fetched = client.get("/objects", params={"digest": obj["digest"]})
    assert fetched.status_code == 200
    assert fetched.json()["content"] == 42

    verified = client.post(
        "/agents/verifier/verify", json={"object": obj["digest"]}
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True


def test_locator_finds_attribute_match(uor):
    _, client = uor
    obj = create_object(client, {"name": "alpha"}, {"kind": "test-object"})

    res = client.post(
        "/agents/locator/query",
        json={"where": {"attributes.kind": "test-object"}},
    )
    assert res.status_code == 200
    digests = {item["digest"] for item in res.json()["matches"]}
    assert obj["digest"] in digests


def test_runtime_registry_seeds_standard_runtimes(uor):
    _, client = uor
    res = client.get("/runtimes")
    assert res.status_code == 200
    names = {runtime["name"] for runtime in res.json()["runtimes"]}
    assert {"sum_contents", "count_inputs", "identity_value"}.issubset(names)


def test_register_runtime_rejects_unsafe_import(uor):
    _, client = uor
    res = client.post(
        "/runtimes/register",
        json={"name": "unsafe", "code": "__import__('os').system('echo bad')"},
    )
    assert res.status_code == 400


def test_execution_produces_output_and_execution_record(uor):
    store, client = uor
    a = create_object(client, 10)
    b = create_object(client, 20)

    res = client.post(
        "/agents/execution/run",
        json={
            "runtimeName": "sum_contents",
            "inputs": [a["digest"], b["digest"]],
            "parameters": {"timeout_seconds": CI_STABLE_TIMEOUT},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["result"] == 30
    assert store.has_object(body["output"])
    assert store.has_object(body["executionRecord"])
    assert store.get_object(body["output"])["content"] == {"result": 30}


def test_lineage_records_execution_event(uor):
    _, client = uor
    a = create_object(client, 1)
    b = create_object(client, 2)
    run = client.post(
        "/agents/execution/run",
        json={
            "runtimeName": "sum_contents",
            "inputs": [a["digest"], b["digest"]],
            "parameters": {"timeout_seconds": CI_STABLE_TIMEOUT},
        },
    ).json()

    trace = client.get(
        "/agents/lineage/trace", params={"digest": run["output"]}
    )
    assert trace.status_code == 200
    events = [event["event"] for event in trace.json()["events"]]
    assert "created" in events
    assert "executed" in events


def test_workflow_chaining_uses_normalized_values(uor):
    _, client = uor
    a = create_object(client, 10)
    b = create_object(client, 20)

    res = client.post(
        "/workflows/run",
        json={
            "name": "chain-normalization",
            "inputs": [a["digest"], b["digest"]],
            "steps": [
                {
                    "runtimeName": "sum_contents",
                    "parameters": {"timeout_seconds": CI_STABLE_TIMEOUT},
                },
                {
                    "runtimeName": "identity_value",
                    "parameters": {"timeout_seconds": CI_STABLE_TIMEOUT},
                },
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["steps"][0]["result"] == 30
    assert body["steps"][1]["result"] == 30


def test_runtime_registry_persists_across_reload(uor):
    store, client = uor
    res = client.post(
        "/runtimes/register",
        json={"name": "triple_sum", "code": "sum(values) * 3"},
    )
    assert res.status_code == 200
    digest = res.json()["runtimeObject"]

    store.reset_in_memory()
    store.load_db()

    assert store.get_runtime_digest("triple_sum") == digest
    assert store.has_object(digest)


def test_constraint_requires_agent_specific_capability(uor):
    _, client = uor
    obj = create_object(client, 1)

    denied = client.post(
        "/agents/constraint/check",
        json={"agent": "verifier", "action": "run", "target": obj["digest"]},
    )
    assert denied.status_code == 200
    assert denied.json()["allowed"] is False

    allowed = client.post(
        "/agents/constraint/check",
        json={
            "agent": "verifier",
            "action": "verify",
            "target": obj["digest"],
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True
