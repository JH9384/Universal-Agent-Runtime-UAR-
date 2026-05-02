from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


def test_streaming_event_sequence():
    with client.stream(
        "POST",
        "/api/uar/stream",
        json={"goal": "stream test", "skills": ["section_sum"]},
    ) as response:
        assert response.status_code == 200

        events = []
        for chunk in response.iter_text():
            if chunk and "data:" in chunk:
                events.append(chunk)

        assert any("start" in e for e in events)
        assert any("skill_start" in e for e in events)
        assert any("skill_complete" in e for e in events)
        assert any("complete" in e for e in events)
