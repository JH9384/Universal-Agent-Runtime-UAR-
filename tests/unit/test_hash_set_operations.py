"""Tests for uar.uor.hash_set_operations."""

from uar.uor.hash_set_operations import (
    ObjectSet,
    HashSetOperations,
    ObjectSetComparison,
)


class TestObjectSet:
    def test_add(self):
        s = ObjectSet()
        d = s.add({"key": "value"})
        assert isinstance(d, str)
        assert d in s.digests
        assert s.contains(d)

    def test_remove(self):
        s = ObjectSet()
        d = s.add({"key": "value"})
        assert s.remove(d) is True
        assert s.remove(d) is False

    def test_get_object(self):
        s = ObjectSet()
        obj = {"key": "value"}
        d = s.add(obj)
        assert s.get_object(d) == obj
        assert s.get_object("nope") is None

    def test_size(self):
        s = ObjectSet()
        assert s.size() == 0
        s.add({"a": 1})
        assert s.size() == 1

    def test_to_digest_list(self):
        s = ObjectSet()
        s.add({"a": 1})
        s.add({"b": 2})
        assert len(s.to_digest_list()) == 2


class TestHashSetOperations:
    def test_create_set(self):
        ops = HashSetOperations()
        s = ops.create_set([{"a": 1}, {"b": 2}])
        assert s.size() == 2

    def test_union(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}])
        b = ops.create_set([{"b": 2}])
        u = ops.union(a, b)
        assert u.size() == 2

    def test_intersection(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}, {"b": 2}])
        b = ops.create_set([{"b": 2}, {"c": 3}])
        i = ops.intersection(a, b)
        assert i.size() == 1

    def test_difference(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}, {"b": 2}])
        b = ops.create_set([{"b": 2}])
        d = ops.difference(a, b)
        assert d.size() == 1

    def test_symmetric_difference(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}, {"b": 2}])
        b = ops.create_set([{"b": 2}, {"c": 3}])
        sd = ops.symmetric_difference(a, b)
        assert sd.size() == 2

    def test_is_subset(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}])
        b = ops.create_set([{"a": 1}, {"b": 2}])
        assert ops.is_subset(a, b) is True
        assert ops.is_subset(b, a) is False

    def test_is_superset(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}, {"b": 2}])
        b = ops.create_set([{"a": 1}])
        assert ops.is_superset(a, b) is True

    def test_are_disjoint(self):
        ops = HashSetOperations()
        a = ops.create_set([{"a": 1}])
        b = ops.create_set([{"b": 2}])
        assert ops.are_disjoint(a, b) is True

    def test_deduplicate_objects(self):
        ops = HashSetOperations()
        result = ops.deduplicate_objects([{"a": 1}, {"a": 1}, {"b": 2}])
        assert len(result) == 2

    def test_find_duplicates(self):
        ops = HashSetOperations()
        result = ops.find_duplicates([{"a": 1}, {"a": 1}, {"b": 2}])
        assert len(result) == 1
        assert len(list(result.values())[0]) == 2

    def test_find_duplicates_none(self):
        ops = HashSetOperations()
        result = ops.find_duplicates([{"a": 1}, {"b": 2}])
        assert len(result) == 0

    def test_compute_set_digest(self):
        ops = HashSetOperations()
        s = ops.create_set([{"a": 1}])
        d = ops.compute_set_digest(s)
        assert d.startswith("sha256:")


class TestObjectSetComparison:
    def test_compare(self):
        comp = ObjectSetComparison()
        a = comp.operations.create_set([{"a": 1}, {"b": 2}])
        b = comp.operations.create_set([{"b": 2}, {"c": 3}])
        result = comp.compare(a, b)
        assert result["set_a_size"] == 2
        assert result["set_b_size"] == 2
        assert result["intersection_size"] == 1
        assert 0 <= result["jaccard_similarity"] <= 1

    def test_find_added_removed(self):
        comp = ObjectSetComparison()
        old = comp.operations.create_set([{"a": 1}])
        new = comp.operations.create_set([{"b": 2}])
        added, removed = comp.find_added_removed(old, new)
        assert len(added) == 1
        assert len(removed) == 1
