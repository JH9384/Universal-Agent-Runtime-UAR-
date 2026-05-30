"""Tests for async UOR object resolution.

Covers AsyncObjectResolver, AsyncObjectProcessor, AsyncBatchValidator.
"""

from unittest.mock import patch

import pytest

from uar.uor.async_resolution import (
    AsyncObjectResolver,
    AsyncObjectProcessor,
    AsyncBatchValidator,
    resolve_objects_async,
)


class TestAsyncObjectResolver:
    """Async object fetching."""

    @pytest.mark.asyncio
    async def test_fetch_object_success(self):
        resolver = AsyncObjectResolver(max_concurrent=2)

        def fetch(digest):
            return {"digest": digest, "data": "test"}

        result = await resolver.fetch_object("abc", fetch)
        assert result == {"digest": "abc", "data": "test"}

    @pytest.mark.asyncio
    async def test_fetch_object_failure(self):
        resolver = AsyncObjectResolver(max_concurrent=2)

        def fetch(digest):
            raise ValueError("boom")

        result = await resolver.fetch_object("abc", fetch)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_objects(self):
        resolver = AsyncObjectResolver(max_concurrent=2)

        def fetch(digest):
            return {"digest": digest}

        results = await resolver.fetch_objects(["a", "b", "c"], fetch)
        assert len(results) == 3
        assert results["a"] == {"digest": "a"}
        assert results["b"] == {"digest": "b"}

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success(self):
        resolver = AsyncObjectResolver(max_concurrent=2)
        calls = 0

        def fetch(digest):
            nonlocal calls
            calls += 1
            if calls < 2:
                return None
            return {"digest": digest}

        result = await resolver.fetch_with_retry(
            "abc", fetch, max_retries=3, backoff=0.01
        )
        assert result == {"digest": "abc"}
        assert calls == 2

    @pytest.mark.asyncio
    async def test_fetch_with_retry_exhausted(self):
        resolver = AsyncObjectResolver(max_concurrent=2)

        def fetch(digest):
            return None

        result = await resolver.fetch_with_retry(
            "abc", fetch, max_retries=2, backoff=0.01
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_retry_exception(self):
        resolver = AsyncObjectResolver(max_concurrent=2)

        with patch.object(
            resolver, "fetch_object", side_effect=RuntimeError("network down")
        ):
            result = await resolver.fetch_with_retry(
                "abc", lambda d: None, max_retries=2, backoff=0.01
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        resolver = AsyncObjectResolver(max_concurrent=1)
        active = 0
        max_active = 0

        def fetch(digest):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            import time

            time.sleep(0.01)
            active -= 1
            return {"digest": digest}

        await resolver.fetch_objects(["a", "b"], fetch)
        assert max_active <= 1


class TestAsyncObjectProcessor:
    """Async object processing."""

    @pytest.mark.asyncio
    async def test_process_object(self):
        processor = AsyncObjectProcessor(max_concurrent=2)

        def process(obj):
            return {**obj, "processed": True}

        result = await processor.process_object({"a": 1}, process)
        assert result["processed"] is True

    @pytest.mark.asyncio
    async def test_process_object_failure(self):
        processor = AsyncObjectProcessor(max_concurrent=2)

        def process(obj):
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await processor.process_object({"a": 1}, process)

    @pytest.mark.asyncio
    async def test_process_objects(self):
        processor = AsyncObjectProcessor(max_concurrent=2)

        def process(obj):
            return obj["value"] * 2

        results = await processor.process_objects(
            [{"value": 1}, {"value": 2}, {"value": 3}], process
        )
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_process_objects_with_exceptions(self):
        processor = AsyncObjectProcessor(max_concurrent=2)

        def process(obj):
            if obj["fail"]:
                raise ValueError("boom")
            return "ok"

        results = await processor.process_objects(
            [{"fail": False}, {"fail": True}], process
        )
        assert results[0] == "ok"
        assert isinstance(results[1], ValueError)


class TestAsyncBatchValidator:
    """Async batch validation."""

    @pytest.mark.asyncio
    async def test_validate_objects(self):
        class FakeValidator:
            def validate_envelope(self, obj):
                return {"valid": True, "obj": obj}

        validator = AsyncBatchValidator(max_concurrent=2)
        objects = [{"a": 1}, {"b": 2}]
        results = await validator.validate_objects(
            objects, FakeValidator()
        )
        assert len(results) == 2
        assert all(r["valid"] for r in results)


class TestResolveObjectsAsync:
    """Convenience function."""

    @pytest.mark.asyncio
    async def test_resolve_multiple(self):
        def fetch(digest):
            return {"id": digest}

        results = await resolve_objects_async(["x", "y"], fetch)
        assert len(results) == 2
        assert results["x"] == {"id": "x"}
