"""Hash-based set operations on UOR object collections.

Provides efficient set operations (union, intersection, difference)
on object collections using content-derived addresses for cryptographic
proof of object inclusion and deduplication.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from .bounded_json import compute_uor_digest

logger = logging.getLogger(__name__)


@dataclass
class ObjectSet:
    """A set of UOR objects indexed by their content-derived addresses."""

    digests: Set[str] = field(default_factory=set)
    objects: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    algorithm: str = "sha256"

    def add(self, obj: Dict[str, Any]) -> str:
        """Add an object to the set.

        Args:
            obj: Object to add

        Returns:
            Digest of the object
        """
        digest = compute_uor_digest(obj, algorithm=self.algorithm)
        self.digests.add(digest)
        self.objects[digest] = obj
        return digest

    def remove(self, digest: str) -> bool:
        """Remove an object by digest.

        Args:
            digest: Digest of object to remove

        Returns:
            True if removed, False if not found
        """
        if digest in self.digests:
            self.digests.remove(digest)
            del self.objects[digest]
            return True
        return False

    def contains(self, digest: str) -> bool:
        """Check if set contains object by digest.

        Args:
            digest: Digest to check

        Returns:
            True if object exists in set
        """
        return digest in self.digests

    def get_object(self, digest: str) -> Optional[Dict[str, Any]]:
        """Get object by digest.

        Args:
            digest: Digest of object to retrieve

        Returns:
            Object data if found, None otherwise
        """
        return self.objects.get(digest)

    def size(self) -> int:
        """Get number of objects in set.

        Returns:
            Size of the set
        """
        return len(self.digests)

    def to_digest_list(self) -> List[str]:
        """Get list of all digests in the set.

        Returns:
            List of digest strings
        """
        return sorted(self.digests)


class HashSetOperations:
    """Hash-based set operations for UOR object collections."""

    def __init__(self, algorithm: str = "sha256"):
        """Initialize hash set operations.

        Args:
            algorithm: Hash algorithm to use for digests
        """
        self.algorithm = algorithm

    def create_set(self, objects: List[Dict[str, Any]]) -> ObjectSet:
        """Create an object set from a list of objects.

        Args:
            objects: List of objects

        Returns:
            ObjectSet with all objects indexed by digest
        """
        obj_set = ObjectSet(algorithm=self.algorithm)
        for obj in objects:
            obj_set.add(obj)
        return obj_set

    def union(self, set_a: ObjectSet, set_b: ObjectSet) -> ObjectSet:
        """Compute union of two object sets.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            New ObjectSet with union of both sets
        """
        result = ObjectSet(algorithm=self.algorithm)
        result.digests = set_a.digests | set_b.digests
        result.objects = {**set_a.objects, **set_b.objects}
        return result

    def intersection(self, set_a: ObjectSet, set_b: ObjectSet) -> ObjectSet:
        """Compute intersection of two object sets.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            New ObjectSet with intersection of both sets
        """
        result = ObjectSet(algorithm=self.algorithm)
        result.digests = set_a.digests & set_b.digests
        for digest in result.digests:
            result.objects[digest] = set_a.objects[digest]
        return result

    def difference(self, set_a: ObjectSet, set_b: ObjectSet) -> ObjectSet:
        """Compute difference of two object sets (set_a - set_b).

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            New ObjectSet with difference (elements in set_a not in set_b)
        """
        result = ObjectSet(algorithm=self.algorithm)
        result.digests = set_a.digests - set_b.digests
        for digest in result.digests:
            result.objects[digest] = set_a.objects[digest]
        return result

    def symmetric_difference(
        self, set_a: ObjectSet, set_b: ObjectSet
    ) -> ObjectSet:
        """Compute symmetric difference of two object sets.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            New ObjectSet with elements in either set but not both
        """
        result = ObjectSet(algorithm=self.algorithm)
        result.digests = set_a.digests ^ set_b.digests
        for digest in result.digests:
            if digest in set_a.objects:
                result.objects[digest] = set_a.objects[digest]
            else:
                result.objects[digest] = set_b.objects[digest]
        return result

    def is_subset(self, set_a: ObjectSet, set_b: ObjectSet) -> bool:
        """Check if set_a is subset of set_b.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            True if set_a is subset of set_b
        """
        return set_a.digests.issubset(set_b.digests)

    def is_superset(self, set_a: ObjectSet, set_b: ObjectSet) -> bool:
        """Check if set_a is superset of set_b.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            True if set_a is superset of set_b
        """
        return set_a.digests.issuperset(set_b.digests)

    def are_disjoint(self, set_a: ObjectSet, set_b: ObjectSet) -> bool:
        """Check if two sets are disjoint.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            True if sets have no elements in common
        """
        return set_a.digests.isdisjoint(set_b.digests)

    def deduplicate_objects(
        self, objects: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate objects from a list.

        Args:
            objects: List of objects (may contain duplicates)

        Returns:
            List of unique objects
        """
        obj_set = self.create_set(objects)
        return [obj_set.objects[digest] for digest in sorted(obj_set.digests)]

    def find_duplicates(
        self, objects: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find duplicate objects in a list.

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

    def compute_set_digest(self, obj_set: ObjectSet) -> str:
        """Compute a digest for the entire object set.

        Args:
            obj_set: Object set to digest

        Returns:
            Digest of the sorted list of object digests
        """
        import hashlib

        sorted_digests = sorted(obj_set.digests)
        combined = "|".join(sorted_digests)
        hash_val = hashlib.sha256(combined.encode()).hexdigest()
        return f"{self.algorithm}:{hash_val}"


class ObjectSetComparison:
    """Compare object sets and provide detailed analysis."""

    def __init__(self, algorithm: str = "sha256"):
        """Initialize object set comparison.

        Args:
            algorithm: Hash algorithm to use for digests
        """
        self.operations = HashSetOperations(algorithm=algorithm)

    def compare(self, set_a: ObjectSet, set_b: ObjectSet) -> Dict[str, Any]:
        """Compare two object sets and provide detailed analysis.

        Args:
            set_a: First object set
            set_b: Second object set

        Returns:
            Dictionary with comparison results
        """
        intersection = self.operations.intersection(set_a, set_b)
        difference_a_b = self.operations.difference(set_a, set_b)
        difference_b_a = self.operations.difference(set_b, set_a)

        union_size = set_a.size() + set_b.size() - intersection.size()
        denominator = union_size if union_size > 0 else 1.0
        jaccard = intersection.size() / denominator
        return {
            "set_a_size": set_a.size(),
            "set_b_size": set_b.size(),
            "intersection_size": intersection.size(),
            "union_size": union_size,
            "only_in_a": difference_a_b.size(),
            "only_in_b": difference_b_a.size(),
            "jaccard_similarity": jaccard,
            "is_subset": self.operations.is_subset(set_a, set_b),
            "is_superset": self.operations.is_superset(set_a, set_b),
            "are_disjoint": self.operations.are_disjoint(set_a, set_b),
        }

    def find_added_removed(
        self, old_set: ObjectSet, new_set: ObjectSet
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Find objects added and removed between two sets.

        Args:
            old_set: Old object set
            new_set: New object set

        Returns:
            Tuple of (added_objects, removed_objects)
        """
        added = self.operations.difference(new_set, old_set)
        removed = self.operations.difference(old_set, new_set)

        added_objects = [added.objects[d] for d in sorted(added.digests)]
        removed_objects = [removed.objects[d] for d in sorted(removed.digests)]

        return added_objects, removed_objects
