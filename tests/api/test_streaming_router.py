"""Tests for uar.api.routers.streaming."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.streaming import router, _stream_binary_visualization


@pytest.fixture
def client():
    app = FastAPI()
    from uar.api.middleware import reset_rate_limiter

    reset_rate_limiter()
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        app.include_router(router)
        return TestClient(app)


@pytest.mark.asyncio
async def test_stream_binary_visualization_no_serializer():
    ws = MagicMock()
    await _stream_binary_visualization(ws, {"skill": "unknown"})
    ws.send_bytes.assert_not_called()


class TestStreamGoal:
    def test_validation_error(self, client):
        response = client.post("/api/uar/stream", json={})
        assert response.status_code == 422
