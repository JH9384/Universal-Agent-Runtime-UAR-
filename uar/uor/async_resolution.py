"""Async I/O for remote UOR object resolution.

Provides asynchronous I/O capabilities for resolving UOR objects
from remote sources, improving performance for concurrent requests.
"""

import logging
from typing import Any, Dict, List, Optional, Callable
import asyncio

logger = logging.getLogger(__name__)


class AsyncObjectResolver:
    """Asynchronous resolver for UOR objects."""

    def __init__(self, max_concurrent: int = 10):
        """Initialize async object resolver.

        Args:
            max_concurrent: Maximum concurrent requests
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_object(
        self, digest: str, fetch_func: Callable[[str], Any]
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single object asynchronously.

        Args:
            digest: Object digest
            fetch_func: Synchronous fetch function

        Returns:
            Object data if successful, None otherwise
        """
        async with self.semaphore:
            try:
                # Run the synchronous fetch function in a thread pool
                loop = asyncio.get_running_loop()
                obj = await loop.run_in_executor(None, fetch_func, digest)
                return obj
            except Exception:
                logger.exception("Failed to fetch object %s", digest)
                return None

    async def fetch_objects(
        self, digests: List[str], fetch_func: Callable[[str], Any]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Fetch multiple objects concurrently.

        Args:
            digests: List of object digests
            fetch_func: Synchronous fetch function

        Returns:
            Dictionary mapping digest to object data
        """
        tasks = [self.fetch_object(digest, fetch_func) for digest in digests]
        results = await asyncio.gather(*tasks)

        return {
            digest: obj
            for digest, obj in zip(digests, results, strict=False)
        }

    async def fetch_with_retry(
        self,
        digest: str,
        fetch_func: Callable[[str], Any],
        max_retries: int = 3,
        backoff: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """Fetch object with retry logic.

        Args:
            digest: Object digest
            fetch_func: Synchronous fetch function
            max_retries: Maximum number of retries
            backoff: Backoff delay between retries

        Returns:
            Object data if successful, None otherwise
        """
        for attempt in range(max_retries):
            try:
                obj = await self.fetch_object(digest, fetch_func)
                if obj is not None:
                    return obj
                logger.warning(
                    "Attempt %s/%s failed for %s",
                    attempt + 1,
                    max_retries,
                    digest,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff * (2**attempt))
            except Exception as e:
                attempt_info = f"Attempt {attempt + 1}/{max_retries} error"
                err_msg = f"{attempt_info} for {digest}: {e}"
                logger.error(err_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff * (2**attempt))

        return None


class AsyncObjectProcessor:
    """Asynchronous processor for UOR objects."""

    def __init__(self, max_concurrent: int = 10):
        """Initialize async object processor.

        Args:
            max_concurrent: Maximum concurrent operations
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_object(
        self,
        obj: Dict[str, Any],
        process_func: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Process a single object asynchronously.

        Args:
            obj: Object to process
            process_func: Synchronous processing function

        Returns:
            Processed result
        """
        async with self.semaphore:
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, process_func, obj)
                return result
            except Exception:
                logger.exception("Failed to process object")
                raise

    async def process_objects(
        self,
        objects: List[Dict[str, Any]],
        process_func: Callable[[Dict[str, Any]], Any],
    ) -> List[Any]:
        """Process multiple objects concurrently.

        Args:
            objects: List of objects to process
            process_func: Synchronous processing function

        Returns:
            List of processed results
        """
        tasks = [self.process_object(obj, process_func) for obj in objects]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results


class AsyncBatchValidator:
    """Asynchronous batch validator for UOR objects."""

    def __init__(self, max_concurrent: int = 10):
        """Initialize async batch validator.

        Args:
            max_concurrent: Maximum concurrent validations
        """
        self.processor = AsyncObjectProcessor(max_concurrent)

    async def validate_objects(
        self,
        objects: List[Dict[str, Any]],
        validator: Any,
    ) -> List[Any]:
        """Validate multiple objects asynchronously.

        Args:
            objects: List of objects to validate
            validator: Validator instance with validate method

        Returns:
            List of validation results
        """

        def validate_single(obj: Dict[str, Any]) -> Any:
            return validator.validate_envelope(obj)

        results = await self.processor.process_objects(
            objects, validate_single
        )
        return results


async def resolve_objects_async(
    digests: List[str], fetch_func: Callable[[str], Any]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Convenience function for async object resolution.

    Args:
        digests: List of object digests
        fetch_func: Synchronous fetch function

    Returns:
        Dictionary mapping digest to object data
    """
    resolver = AsyncObjectResolver()
    return await resolver.fetch_objects(digests, fetch_func)
