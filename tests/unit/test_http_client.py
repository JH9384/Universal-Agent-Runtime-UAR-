"""Tests for uar.core.http_client."""

from unittest.mock import MagicMock, patch

import pytest

from uar.core.http_client import (
    _get_session,
    http_get,
    http_post,
    close_all_sessions,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    from uar.core.http_client import _sessions

    _sessions.clear()
    yield
    _sessions.clear()


@pytest.mark.asyncio
async def test_get_session_no_aiohttp():
    with patch.dict("sys.modules", {"aiohttp": None}):
        sess = await _get_session("http://example.com")
    assert sess is None


@pytest.mark.asyncio
async def test_get_session_creates():
    fake_aiohttp = type(
        "aiohttp",
        (),
        {
            "ClientSession": type(
                "CS", (), {"__init__": lambda self, **k: None}
            ),
            "TCPConnector": type(
                "TC", (), {"__init__": lambda self, **k: None}
            ),
            "ClientTimeout": type(
                "CT", (), {"__init__": lambda self, **k: None}
            ),
        },
    )()
    with patch.dict("sys.modules", {"aiohttp": fake_aiohttp}):
        sess = await _get_session("http://example.com")
    assert sess is not None


@pytest.mark.asyncio
async def test_get_session_reuses():
    fake_aiohttp = type(
        "aiohttp",
        (),
        {
            "ClientSession": type(
                "CS", (), {"__init__": lambda self, **k: None}
            ),
            "TCPConnector": type(
                "TC", (), {"__init__": lambda self, **k: None}
            ),
            "ClientTimeout": type(
                "CT", (), {"__init__": lambda self, **k: None}
            ),
        },
    )()
    with patch.dict("sys.modules", {"aiohttp": fake_aiohttp}):
        s1 = await _get_session("http://example.com")
        s2 = await _get_session("http://example.com")
    assert s1 is s2


@pytest.mark.asyncio
async def test_http_get_no_aiohttp():
    with patch.dict("sys.modules", {"aiohttp": None}):
        with pytest.raises(RuntimeError, match="aiohttp"):
            await http_get("http://example.com")


@pytest.mark.asyncio
async def test_http_post_no_aiohttp():
    with patch.dict("sys.modules", {"aiohttp": None}):
        with pytest.raises(RuntimeError, match="aiohttp"):
            await http_post("http://example.com")


def test_close_all_sessions():
    from uar.core.http_client import _sessions

    mock_sess = MagicMock()
    _sessions["example.com"] = mock_sess
    close_all_sessions()
    assert "example.com" not in _sessions


def test_close_all_sessions_exception():
    from uar.core.http_client import _sessions

    bad_sess = MagicMock()
    bad_sess.close.side_effect = RuntimeError("close failed")
    _sessions["bad.com"] = bad_sess
    close_all_sessions()
    assert "bad.com" not in _sessions


class _AsyncCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *args):
        return None


def _async_json(value):
    async def _json():
        return value
    return _json


@pytest.mark.asyncio
async def test_http_get_success():
    mock_resp = MagicMock()
    mock_resp.json = _async_json("async for result")

    class FakeSession:
        def get(self, url, **kw):
            return _AsyncCtx(mock_resp)

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        result = await http_get("http://example.com")
    assert result == "async for result"


@pytest.mark.asyncio
async def test_http_post_success():
    mock_resp = MagicMock()
    mock_resp.json = _async_json("async for result")

    class FakeSession:
        def post(self, url, **kw):
            return _AsyncCtx(mock_resp)

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        result = await http_post("http://example.com", json_data={"k": "v"})
    assert result == "async for result"


@pytest.mark.asyncio
async def test_http_get_retry_then_success():
    mock_resp = MagicMock()
    mock_resp.json = _async_json("ok")
    call_count = 0

    class FakeSession:
        def get(self, url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("fail")
            return _AsyncCtx(mock_resp)

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            result = await http_get("http://example.com")
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_http_get_all_retries_fail():
    class FakeSession:
        def get(self, url, **kw):
            raise ConnectionError("always fails")

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(ConnectionError):
                await http_get("http://example.com")
