"""Tests for uar.core.async_utils.

Covers run_sync_safe in all three modes: no-loop, running-loop, and
exception propagation.
"""

import asyncio

import pytest

from uar.core.async_utils import run_sync_safe


async def _dummy_coro(value: str) -> str:
    await asyncio.sleep(0)
    return value


async def _failing_coro() -> None:
    await asyncio.sleep(0)
    raise RuntimeError("boom")


class TestRunSyncSafe:
    """run_sync_safe behaviour across loop contexts."""

    def test_no_running_loop(self):
        """When no loop is running, delegates to asyncio.run()."""
        result = run_sync_safe(_dummy_coro("hello"))
        assert result == "hello"

    def test_from_running_loop(self):
        """When called from a running loop, uses a dedicated thread."""
        results = []

        async def _inner():
            result = run_sync_safe(_dummy_coro("world"))
            results.append(result)

        asyncio.run(_inner())
        assert results == ["world"]

    def test_exception_propagated(self):
        """Exceptions from the coroutine are re-raised in caller."""
        with pytest.raises(RuntimeError, match="boom"):
            run_sync_safe(_failing_coro())

    def test_exception_from_running_loop(self):
        """Exceptions propagate correctly even from a running loop."""
        errors = []

        async def _inner():
            try:
                run_sync_safe(_failing_coro())
            except RuntimeError as exc:
                errors.append(str(exc))

        asyncio.run(_inner())
        assert errors == ["boom"]

    def test_coroutine_closed_on_exception(self):
        """Coroutine object is closed so async resources are cleaned up."""
        coro = _failing_coro()
        try:
            run_sync_safe(coro)
        except RuntimeError:
            pass
        # closed() returns True after close()
        assert coro.cr_frame is None

    def test_nested_async_context_manager(self):
        """Async context managers inside the coroutine are torn down."""
        entered = []
        exited = []

        class _Tracker:
            async def __aenter__(self):
                entered.append(1)
                return self

            async def __aexit__(self, *args):
                exited.append(1)
                return False

        async def _with_cm():
            async with _Tracker():
                raise RuntimeError("inside cm")

        with pytest.raises(RuntimeError, match="inside cm"):
            run_sync_safe(_with_cm())

        assert entered == [1]
        assert exited == [1]

