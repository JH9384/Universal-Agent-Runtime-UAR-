from fastapi.testclient import TestClient

from fastapi import FastAPI

from uar.runtime.ws.server import router


app = FastAPI()
app.include_router(router)


def test_runtime_websocket_stream() -> None:
    client = TestClient(app)

    with client.websocket_connect('/ws/runtime') as websocket:
        payload = websocket.receive_json()

    assert payload['event_type'] == 'fabric.health'
