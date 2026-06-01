"""Batch operations for bulk UOR object processing.

Provides efficient batch operations for processing multiple UOR objects,
including validation, digest computation, and transformation.
"""

import atexit
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from .bounded_json import compute_uor_digest, canonicalize_json
from .schema_validation import UORSchemaValidator

logger = logging.getLogger(__name__)

# Module-level shared pool to avoid per-batch thread churn
_BATCH_POOL_MAX = max(
    1, int(os.getenv("UOR_BATCH_POOL_SIZE", "8").strip() or "8")
)
_batch_pool: Optional[ThreadPoolExecutor] = None
_batch_pool_shutdown = False
_batch_pool_lock = threading.Lock()


def _get_batch_pool() -> ThreadPoolExecutor:
    global _batch_pool, _batch_pool_shutdown
    if _batch_pool is not None and not _batch_pool_shutdown:
        return _batch_pool
    with _batch_pool_lock:
        if _batch_pool is not None and not _batch_pool_shutdown:
            return _batch_pool
        if _batch_pool_shutdown:
            # Pool was shut down (e.g. by atexit) while we were waiting
            # for the lock; do not recreate — let the caller handle it.
            _batch_pool = ThreadPoolExecutor(
                max_workers=_BATCH_POOL_MAX,
                thread_name_prefix="uar-batch",
            )
            _batch_pool_shutdown = False
        else:
            _batch_pool = ThreadPoolExecutor(
                max_workers=_BATCH_POOL_MAX,
                thread_name_prefix="uar-batch",
            )
            _batch_pool_shutdown = False
    return _batch_pool


def _shutdown_batch_pool():
    global _batch_pool_shutdown
    with _batch_pool_lock:
        if _batch_pool is not None:
            _batch_pool.shutdown(wait=False)
        _batch_pool_shutdown = True


atexit.register(_shutdown_batch_pool)


@dataclass
class BatchResult:
    """Result of a batch operation."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    errors: List[Tuple[int, str]] = field(default_factory=list)
    results: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "errors": self.errors,
            "results": self.results,
        }


class BatchProcessor:
    """Batch processor for UOR objects."""

    def __init__(self, max_workers: int = 4):
        """Initialize batch processor.

        Args:
            max_workers: Maximum number of parallel workers.
                Uses shared pool if max_workers <= _BATCH_POOL_MAX.
        """
        self.max_workers = max_workers
        if max_workers <= _BATCH_POOL_MAX:
            self._pool = _get_batch_pool()
            self._owns_pool = False
        else:
            self._pool = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="uar-batch-dedicated",
            )
            self._owns_pool = True

    def close(self) -> None:
        """Shut down the dedicated pool if this processor owns one."""
        if self._owns_pool and self._pool is not None:
            self._pool.shutdown(wait=False)

    def batch_compute_digests(
        self, objects: List[Dict[str, Any]], algorithm: str = "sha256"
    ) -> BatchResult:
        """Compute digests for multiple objects in batch.

        Args:
            objects: List of objects to digest
            algorithm: Hash algorithm to use

        Returns:
            BatchResult with digest results
        """
        result = BatchResult(total=len(objects))

        futures = {
            self._pool.submit(
                self._compute_single_digest,
                obj,
                algorithm,
                i,
            ): i
            for i, obj in enumerate(objects)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                digest = future.result()
                result.results.append({"index": idx, "digest": digest})
                result.successful += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append(
                    (idx, f"Digest computation failed: {exc}")
                )
                logger.exception(
                    "Failed to compute digest for object %s", idx
                )

        return result

    def _compute_single_digest(
        self, obj: Dict[str, Any], algorithm: str, index: int
    ) -> str:
        """Compute digest for a single object.

        Args:
            obj: Object to digest
            algorithm: Hash algorithm
            index: Object index

        Returns:
            Digest string
        """
        return compute_uor_digest(obj, algorithm)

    def batch_validate(
        self,
        objects: List[Dict[str, Any]],
        validator: Optional[UORSchemaValidator] = None,
    ) -> BatchResult:
        """Validate multiple objects in batch.

        Args:
            objects: List of objects to validate
            validator: Schema validator instance

        Returns:
            BatchResult with validation results
        """
        result = BatchResult(total=len(objects))

        if validator is None:
            validator = UORSchemaValidator()

        futures = {
            self._pool.submit(
                self._validate_single,
                obj,
                validator,
                i,
            ): i
            for i, obj in enumerate(objects)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                is_valid, errors = future.result()
                result.results.append(
                    {
                        "index": idx,
                        "valid": is_valid,
                        "errors": errors,
                    }
                )
                if is_valid:
                    result.successful += 1
                else:
                    result.failed += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append((idx, f"Validation failed: {exc}"))
                logger.exception(
                    "Failed to validate object %s", idx
                )

        return result

    def _validate_single(
        self,
        obj: Dict[str, Any],
        validator: UORSchemaValidator,
        index: int,
    ) -> Tuple[bool, List[str]]:
        """Validate a single object.

        Args:
            obj: Object to validate
            validator: Schema validator
            index: Object index

        Returns:
            Tuple of (is_valid, errors)
        """
        is_valid, errors = validator.validate_envelope(obj)
        return is_valid, errors

    def batch_transform(
        self,
        objects: List[Dict[str, Any]],
        transform_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> BatchResult:
        """Transform multiple objects in batch.

        Args:
            objects: List of objects to transform
            transform_func: Function to apply to each object

        Returns:
            BatchResult with transformation results
        """
        result = BatchResult(total=len(objects))

        futures = {
            self._pool.submit(
                self._transform_single,
                obj,
                transform_func,
                i,
            ): i
            for i, obj in enumerate(objects)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                transformed = future.result()
                result.results.append(
                    {"index": idx, "object": transformed}
                )
                result.successful += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append((idx, f"Transformation failed: {exc}"))
                logger.exception(
                    "Failed to transform object %s", idx
                )

        return result

    def _transform_single(
        self,
        obj: Dict[str, Any],
        transform_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        index: int,
    ) -> Dict[str, Any]:
        """Transform a single object.

        Args:
            obj: Object to transform
            transform_func: Transformation function
            index: Object index

        Returns:
            Transformed object
        """
        return transform_func(obj)

    def batch_canonicalize(self, objects: List[Dict[str, Any]]) -> BatchResult:
        """Canonicalize multiple objects in batch.

        Args:
            objects: List of objects to canonicalize

        Returns:
            BatchResult with canonicalization results
        """
        result = BatchResult(total=len(objects))

        futures = {
            self._pool.submit(
                self._canonicalize_single,
                obj,
                i,
            ): i
            for i, obj in enumerate(objects)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                canonical = future.result()
                result.results.append(
                    {"index": idx, "canonical": canonical}
                )
                result.successful += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append((idx, f"Canonicalization failed: {exc}"))
                logger.exception(
                    "Failed to canonicalize object %s", idx
                )

        return result

    def _canonicalize_single(self, obj: Dict[str, Any], index: int) -> str:
        """Canonicalize a single object.

        Args:
            obj: Object to canonicalize
            index: Object index

        Returns:
            Canonical JSON string
        """
        return canonicalize_json(obj)


class BatchDeduplicator:
    """Batch deduplication for UOR objects."""

    def __init__(self, algorithm: str = "sha256"):
        """Initialize batch deduplicator.

        Args:
            algorithm: Hash algorithm for digest computation
        """
        self.algorithm = algorithm

    def deduplicate(
        self, objects: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
        """Remove duplicate objects from a list.

        Args:
            objects: List of objects (may contain duplicates)

        Returns:
            Tuple of (unique_objects, duplicate_indices)
            where duplicate_indices maps digest to list of indices
        """
        digest_map: Dict[str, List[int]] = {}
        for i, obj in enumerate(objects):
            digest = compute_uor_digest(obj, algorithm=self.algorithm)
            if digest not in digest_map:
                digest_map[digest] = []
            digest_map[digest].append(i)

        # Get unique objects (first occurrence of each digest),
        # preserving insertion order — do NOT sort by digest hash.
        unique_objects = []
        for _digest, indices in digest_map.items():
            unique_objects.append(objects[indices[0]])

        # Find duplicates (indices beyond the first)
        duplicate_indices = {
            digest: indices[1:]
            for digest, indices in digest_map.items()
            if len(indices) > 1
        }

        return unique_objects, duplicate_indices

    def find_duplicates(
        self, objects: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find all duplicate objects.

        Args:
            objects: List of objects

        Returns:
            Dictionary mapping digest to list of duplicate objects
        """
        digest_map: Dict[str, List[Dict[str, Any]]] = {}
        for obj in objects:
            digest = compute_uor_digest(obj, algorithm=self.algorithm)
            if digest not in digest_map:
                digest_map[digest] = []
            digest_map[digest].append(obj)

        # Return only duplicates
        return {d: objs for d, objs in digest_map.items() if len(objs) > 1}
