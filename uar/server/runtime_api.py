from __future__ import annotations

from typing import Any, Dict, List

try:
    from fastapi import FastAPI, WebSocket
except Exception:  # pragma: no cover - allows core import without optional deps
    FastAPI = None  # type: ignore[assignment]
    WebSocket = None  # type: ignore[assignment]

from uar.core.runtime_health import RuntimeHealthStatus
from uar.core.runtime_telemetry import RuntimeTelemetryBuffer
from uar.core.runtime_transport import RuntimeTransportBuffer


telemetry = RuntimeTelemetryBuffer()
transport = RuntimeTransportBuffer()


if FastAPI is not None:
    app = FastAPI(title="UAR Runtime API", version="0.1.0")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return RuntimeHealthStatus().to_dict()

    @app.get("/telemetry")
    def telemetry_snapshot() -> List[Dict[str, Any]]:
        return telemetry.snapshot()

    @app.post("/emit/{category}")
    def emit(category: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = telemetry.emit(category, payload)
        envelope = transport.send(topic=category, payload=payload)
        return {
            "event": event.to_dict(),
            "transport": envelope.to_dict(),
        }

    @app.websocket("/ws/runtime")
    async def runtime_socket(websocket: WebSocket) -> None:  # type: ignore[valid-type]
        await websocket.accept()
        await websocket.send_json({"type": "runtime.ready"})
        while True:
            message = await websocket.receive_json()
            category = str(message.get("category", "runtime.message"))
            payload = dict(message.get("payload", {}))
            event = telemetry.emit(category, payload)
            await websocket.send_json({"type": "runtime.event", "event": event.to_dict()})
else:
    app = None
