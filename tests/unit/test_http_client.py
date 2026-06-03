"""Tests for uar.core.http_client."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from uar.core.http_client import (
    _get_session,
    http_get,
    http_post,
    close_all_sessions,
)
from uar.core.exceptions import ValidationError


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


@pytest.mark.asyncio
async def test_close_all_sessions():
    from uar.core.http_client import _sessions

    mock_sess = MagicMock()
    _sessions["example.com"] = mock_sess
    await close_all_sessions()
    assert "example.com" not in _sessions


@pytest.mark.asyncio
async def test_close_all_sessions_exception():
    from uar.core.http_client import _sessions

    bad_sess = MagicMock()
    bad_sess.close.side_effect = RuntimeError("close failed")
    _sessions["bad.com"] = bad_sess
    await close_all_sessions()
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


@pytest.mark.asyncio
async def test_http_get_max_retries_zero():
    class FakeSession:
        def get(self, url, **kw):
            raise ConnectionError("fail")

    with patch("uar.core.http_client._MAX_RETRIES", 0):
        with patch("uar.core.http_client._get_session") as m:
            m.return_value = FakeSession()
            with pytest.raises(RuntimeError, match="No attempts made"):
                await http_get("http://example.com")


@pytest.mark.asyncio
async def test_http_post_all_retries_fail():
    class FakeSession:
        def post(self, url, **kw):
            raise ConnectionError("always fails")

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(ConnectionError):
                await http_post("http://example.com")


@pytest.mark.asyncio
async def test_http_post_max_retries_zero():
    class FakeSession:
        def post(self, url, **kw):
            raise ConnectionError("fail")

    with patch("uar.core.http_client._MAX_RETRIES", 0):
        with patch("uar.core.http_client._get_session") as m:
            m.return_value = FakeSession()
            with pytest.raises(RuntimeError, match="No attempts made"):
                await http_post("http://example.com")


# --- SSRF prevention tests ---


@pytest.mark.asyncio
async def test_http_get_blocks_private_ip():
    with pytest.raises(ValidationError):
        await http_get("http://192.168.1.1/internal")


@pytest.mark.asyncio
async def test_http_get_blocks_localhost():
    with pytest.raises(ValidationError):
        await http_get("http://localhost:8000/api")


@pytest.mark.asyncio
async def test_http_post_blocks_private_ip():
    with pytest.raises(ValidationError):
        await http_post("http://10.0.0.1/internal", json_data={})


@pytest.mark.asyncio
async def test_http_post_blocks_loopback():
    with pytest.raises(ValidationError):
        await http_post("http://127.0.0.1:8000/api", json_data={})


class TestSessionCacheThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_get_and_close_sessions(self):
        """Regression: _get_session fast path must not race close_all_sessions.

        The fast path used `if domain in _sessions: return _sessions[domain]`
        outside the lock.  Concurrent close_all_sessions could delete the key
        between the check and the access, causing KeyError.
        """
        import asyncio

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
            # Pre-warm a session
            await _get_session("http://example.com")

            errors = []
            stop = asyncio.Event()

            async def getter():
                try:
                    while not stop.is_set():
                        await _get_session("http://example.com")
                        await asyncio.sleep(0)
                except Exception as exc:
                    errors.append(exc)

            async def closer():
                for _ in range(200):
                    await close_all_sessions()
                    await asyncio.sleep(0)

            getters = [asyncio.create_task(getter()) for _ in range(3)]
            closers = [asyncio.create_task(closer()) for _ in range(2)]

            await asyncio.wait_for(
                asyncio.gather(*closers, return_exceptions=True), timeout=10
            )
            stop.set()
            await asyncio.gather(*getters, return_exceptions=True)

            assert not errors, f"Thread-safety regression: {errors}"


@pytest.mark.asyncio
async def test_get_session_evicts_oldest_when_at_capacity():
    """Regression: _sessions must not grow unbounded."""
    from uar.core.http_client import _sessions

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
        with patch("uar.core.http_client._MAX_SESSIONS", 2):
            s1 = await _get_session("http://alpha.com")
            s2 = await _get_session("http://beta.com")
            s3 = await _get_session("http://gamma.com")

    assert s1 is not s2 is not s3
    # Oldest (alpha) should have been evicted
    assert "alpha.com" not in _sessions
    assert "beta.com" in _sessions
    assert "gamma.com" in _sessions


@pytest.mark.asyncio
async def test_http_get_raise_for_status_on_non_2xx():
    """Regression: non-2xx responses must raise before json() is parsed."""
    mock_resp = MagicMock()
    mock_resp.json = _async_json("error body")
    mock_resp.raise_for_status.side_effect = RuntimeError("HTTP 500")

    class FakeSession:
        def get(self, url, **kw):
            return _AsyncCtx(mock_resp)

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(RuntimeError, match="HTTP 500"):
                await http_get("http://example.com")


@pytest.mark.asyncio
async def test_http_post_raise_for_status_on_non_2xx():
    """Regression: non-2xx responses must raise before json() is parsed."""
    mock_resp = MagicMock()
    mock_resp.json = _async_json("error body")
    mock_resp.raise_for_status.side_effect = RuntimeError("HTTP 503")

    class FakeSession:
        def post(self, url, **kw):
            return _AsyncCtx(mock_resp)

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(RuntimeError, match="HTTP 503"):
                await http_post("http://example.com", json_data={})


@pytest.mark.asyncio
async def test_http_get_does_not_retry_4xx():
    """Regression: 4xx client errors must not be retried."""
    exc = RuntimeError("HTTP 404")
    exc.status = 404

    class FakeSession:
        def get(self, url, **kw):
            raise exc

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(RuntimeError, match="HTTP 404"):
                await http_get("http://example.com")
    # If retries had happened, sleep would have been called
    # (patch above would return None, but call_count would be > 0)


@pytest.mark.asyncio
async def test_http_post_does_not_retry_4xx():
    """Regression: 4xx client errors must not be retried."""
    exc = RuntimeError("HTTP 403")
    exc.status = 403

    class FakeSession:
        def post(self, url, **kw):
            raise exc

    with patch("uar.core.http_client._get_session") as m:
        m.return_value = FakeSession()
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(RuntimeError, match="HTTP 403"):
                await http_post("http://example.com", json_data={})


@pytest.mark.asyncio
async def test_get_session_eviction_does_not_race_fast_path():
    """Regression: session closed while another coroutine uses it.

    The fast path returns a reference without holding the lock.
    If eviction happens under the same lock and closes that session,
    the fast-path coroutine crashes with a closed session.
    """
    class _FakeAiohttpSession:
        def __init__(self, **kw):
            self._closed = False

        async def close(self):
            self._closed = True

    fake_aiohttp = type(
        "aiohttp",
        (),
        {
            "ClientSession": _FakeAiohttpSession,
            "TCPConnector": type(
                "TC", (), {"__init__": lambda self, **k: None}
            ),
            "ClientTimeout": type(
                "CT", (), {"__init__": lambda self, **k: None}
            ),
        },
    )()

    with patch.dict("sys.modules", {"aiohttp": fake_aiohttp}):
        with patch("uar.core.http_client._MAX_SESSIONS", 2):
            # Pre-warm two sessions
            await _get_session("http://alpha.com")
            await _get_session("http://beta.com")

            errors = []
            stop = asyncio.Event()

            async def getter():
                try:
                    while not stop.is_set():
                        sess = await _get_session("http://alpha.com")
                        if sess._closed:
                            errors.append("session was closed")
                        await asyncio.sleep(0)
                except Exception as exc:
                    errors.append(str(exc))

            async def evicter():
                for _ in range(200):
                    # Force eviction by creating new-domain sessions
                    await _get_session("http://gamma.com")
                    await _get_session("http://delta.com")
                    await asyncio.sleep(0)

            getters = [asyncio.create_task(getter()) for _ in range(3)]
            evicters = [asyncio.create_task(evicter()) for _ in range(2)]

            await asyncio.wait_for(
                asyncio.gather(*evicters, return_exceptions=True), timeout=10
            )
            stop.set()
            await asyncio.gather(*getters, return_exceptions=True)

            assert not errors, f"Eviction race regression: {errors}"
