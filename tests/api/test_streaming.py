import json
import tempfile

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


def _read_sse_events(response):
    events = []
    for chunk in response.iter_text():
        if not chunk:
            continue
        for frame in chunk.strip().split("\n\n"):
            lines = frame.splitlines()
            data_lines = [
                line.removeprefix("data: ")
                for line in lines
                if line.startswith("data: ")
            ]
            if data_lines:
                events.append(json.loads("".join(data_lines)))
    return events


def test_streaming_event_sequence():
    with client.stream(
        "POST",
        "/api/uar/stream",
        json={"goal": "stream test", "skills": ["section_sum"]},
    ) as response:
        assert response.status_code == 200
        events = _read_sse_events(response)

    event_types = [event["type"] for event in events]
    assert event_types[0] == "orchestration_plan"
    assert event_types[1] == "start"
    assert "skill_start" in event_types
    assert "skill_complete" in event_types
    assert event_types[-1] == "complete"


def test_streaming_event_contract_shape():
    with client.stream(
        "POST",
        "/api/uar/stream",
        json={"goal": "contract test", "skills": ["section_sum"]},
    ) as response:
        assert response.status_code == 200
        events = _read_sse_events(response)

    required_keys = {
        "schema_version",
        "type",
        "run_id",
        "goal_id",
        "skill",
        "timestamp",
        "payload",
        "error",
    }
    for event in events:
        assert required_keys.issubset(event.keys())
        assert event["schema_version"] == "uar.event.v1"


def test_run_and_stream_final_output_parity():
    payload = {"goal": "parity test", "skills": ["section_sum"]}

    run_response = client.post("/api/uar/run", json=payload)
    assert run_response.status_code == 200
    run_record = run_response.json()

    with client.stream(
        "POST", "/api/uar/stream", json=payload
    ) as stream_response:
        assert stream_response.status_code == 200
        events = _read_sse_events(stream_response)

    complete_event = events[-1]
    stream_payload = complete_event["payload"]

    assert run_record["status"] == stream_payload["status"]
    assert run_record["outputs"] == stream_payload["outputs"]
    assert run_record["final_context"] == stream_payload["final_context"]


def test_stream_persists_without_duplicate_execution():
    import os

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("Store-mutation test not safe under xdist")

    # Reset container to a fresh JsonRunStore for this test
    from uar.api.state import set_service_container
    from uar.container import ServiceContainer
    from uar.memory.json_store import JsonRunStore

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as f:
        tmp_path = f.name
    try:
        container = ServiceContainer()
        container._store = JsonRunStore(path=tmp_path)
        set_service_container(container)

        before = client.get("/api/uar/runs").json()["data"]["items"]

        with client.stream(
            "POST",
            "/api/uar/stream",
            json={"goal": "single execution", "skills": ["section_sum"]},
        ) as response:
            assert response.status_code == 200
            _read_sse_events(response)

        after = client.get("/api/uar/runs").json()["data"]["items"]
        assert len(after) == len(before) + 1
    finally:
        os.unlink(tmp_path)
