from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket('/ws/runtime')
async def runtime_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    await websocket.send_json(
        {
            'event_type': 'fabric.health',
            'payload': {
                'overall_score': 0.95,
                'anomaly_count': 0,
            },
        }
    )

    await websocket.close()
