"""Tests for UOR batch operations.

Covers BatchProcessor, BatchDeduplicator, BatchResult.
"""

from uar.uor.batch_operations import (
    BatchResult,
    BatchProcessor,
    BatchDeduplicator,
)


class TestBatchResult:
    """BatchResult dataclass."""

    def test_defaults(self):
        r = BatchResult()
        assert r.total == 0
        assert r.successful == 0
        assert r.failed == 0
        assert r.errors == []
        assert r.results == []

    def test_to_dict(self):
        r = BatchResult(total=3, successful=2, failed=1)
        d = r.to_dict()
        assert d["total"] == 3
        assert d["successful"] == 2
        assert d["failed"] == 1


class TestBatchProcessor:
    """Batch processing of UOR objects."""

    def test_batch_compute_digests(self):
        bp = BatchProcessor(max_workers=2)
        objects = [{"a": 1}, {"b": 2}, {"c": 3}]
        result = bp.batch_compute_digests(objects)
        assert result.total == 3
        assert result.successful == 3
        assert result.failed == 0
        assert len(result.results) == 3
        # Each result has index and digest
        assert all("digest" in r for r in result.results)

    def test_batch_compute_digests_empty(self):
        bp = BatchProcessor(max_workers=2)
        result = bp.batch_compute_digests([])
        assert result.total == 0
        assert result.successful == 0

    def test_batch_validate(self):
        bp = BatchProcessor(max_workers=2)
        objects = [
            {"content": {"a": 1}, "digest": "wrong"},
            {"content": {"b": 2}},
        ]
        result = bp.batch_validate(objects)
        assert result.total == 2
        # Results exist even if validation fails
        assert len(result.results) == 2

    def test_batch_transform(self):
        bp = BatchProcessor(max_workers=2)

        def double_value(obj):
            return {**obj, "value": obj["value"] * 2}

        objects = [{"value": 1}, {"value": 2}, {"value": 3}]
        result = bp.batch_transform(objects, double_value)
        assert result.total == 3
        assert result.successful == 3
        assert len(result.results) == 3
        values = [r["object"]["value"] for r in result.results]
        assert sorted(values) == [2, 4, 6]

    def test_batch_transform_failure(self):
        bp = BatchProcessor(max_workers=2)

        def bad_transform(obj):
            if obj["fail"]:
                raise ValueError("boom")
            return obj

        objects = [{"fail": False}, {"fail": True}]
        result = bp.batch_transform(objects, bad_transform)
        assert result.total == 2
        assert result.successful == 1
        assert result.failed == 1
        assert len(result.errors) == 1

    def test_batch_canonicalize(self):
        bp = BatchProcessor(max_workers=2)
        objects = [{"b": 2, "a": 1}, {"d": 4, "c": 3}]
        result = bp.batch_canonicalize(objects)
        assert result.total == 2
        assert result.successful == 2
        assert len(result.results) == 2
        # Canonical JSON should have sorted keys
        for r in result.results:
            assert "canonical" in r


class TestBatchDeduplicator:
    """Deduplication of UOR objects."""

    def test_no_duplicates(self):
        dd = BatchDeduplicator()
        objects = [{"a": 1}, {"b": 2}, {"c": 3}]
        unique, duplicates = dd.deduplicate(objects)
        assert len(unique) == 3
        assert duplicates == {}

    def test_with_duplicates(self):
        dd = BatchDeduplicator()
        objects = [{"a": 1}, {"a": 1}, {"b": 2}]
        unique, duplicates = dd.deduplicate(objects)
        assert len(unique) == 2
        assert len(duplicates) == 1
        # duplicate indices should be [1] (second occurrence)
        for indices in duplicates.values():
            assert indices == [1]

    def test_find_duplicates(self):
        dd = BatchDeduplicator()
        objects = [{"a": 1}, {"a": 1}, {"b": 2}]
        result = dd.find_duplicates(objects)
        assert len(result) == 1
        for digest, objs in result.items():
            assert len(objs) == 2
