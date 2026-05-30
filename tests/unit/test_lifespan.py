"""Tests for uar.api.lifespan."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from uar.api.lifespan import _retention_purge_loop, create_lifespan


@pytest.mark.asyncio
async def test_retention_purge_loop_cancelled():
    task = asyncio.create_task(_retention_purge_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_retention_purge_loop_negative_retention():
    with patch("uar.config.config") as mock_cfg:
        mock_cfg.run_retention_days = -1
        await _retention_purge_loop()


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown():
    counter = MagicMock()
    counter.count = 0
    lifespan = create_lifespan(counter)

    from fastapi import FastAPI

    app = FastAPI(lifespan=lifespan)
    with patch.dict("sys.modules", {"opentelemetry": None}):
        async with lifespan(app):
            pass
