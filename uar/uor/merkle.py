"""Merkle tree construction for UOR object collections.

Provides Merkle tree capabilities for efficient object set operations,
cryptographic proof of inclusion, and delta encoding between versions.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MerkleNode:
    """Node in a Merkle tree."""

    digest: str
    left: Optional["MerkleNode"]
    right: Optional["MerkleNode"]
    data: Optional[Any] = None
    is_leaf: bool = False


@dataclass
class MerkleProof:
    """Merkle proof for inclusion verification."""

    target_digest: str
    proof: List[Tuple[str, str]]  # (sibling_digest, direction)
    root_digest: str


class UORMerkleTree:
    """Merkle tree for UOR object collections."""

    def __init__(self, hash_algorithm: str = "sha256"):
        """Initialize Merkle tree with hash algorithm.

        Args:
            hash_algorithm: Hash algorithm to use (default sha256)
        """
        self.hash_algorithm = hash_algorithm
        self.root: Optional[MerkleNode] = None
        self.leaves: Dict[str, MerkleNode] = {}

    def _hash(self, data: bytes) -> str:
        """Compute hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex digest
        """
        if self.hash_algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif self.hash_algorithm == "sha3-256":
            return hashlib.sha3_256(data).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {self.hash_algorithm}")

    def _hash_pair(self, left: str, right: str) -> str:
        """Hash pair of digests.

        Args:
            left: Left digest
            right: Right digest

        Returns:
            Combined hash
        """
        combined = left + right
        return self._hash(combined.encode("utf-8"))

    def build_tree(self, digests: List[str]) -> MerkleNode:
        """Build Merkle tree from list of digests.

        Args:
            digests: List of object digests

        Returns:
            Root node of Merkle tree
        """
        if not digests:
            raise ValueError("Cannot build tree from empty digest list")

        # Create leaf nodes
        nodes = []
        self.leaves = {}

        for digest in digests:
            node = MerkleNode(
                digest=digest,
                left=None,
                right=None,
                data=digest,
                is_leaf=True,
            )
            nodes.append(node)
            self.leaves[digest] = node

        # Build tree bottom-up
        while len(nodes) > 1:
            new_level = []
            # Handle odd number of nodes by duplicating last
            if len(nodes) % 2 == 1:
                nodes.append(nodes[-1])

            for i in range(0, len(nodes), 2):
                left = nodes[i]
                right = nodes[i + 1]
                combined_digest = self._hash_pair(left.digest, right.digest)

                parent = MerkleNode(
                    digest=combined_digest,
                    left=left,
                    right=right,
                    is_leaf=False,
                )
                new_level.append(parent)

            nodes = new_level

        self.root = nodes[0]
        return self.root

    def get_root_digest(self) -> Optional[str]:
        """Get root digest of the tree.

        Returns:
            Root digest or None if tree not built
        """
        return self.root.digest if self.root else None

    def generate_proof(self, digest: str) -> Optional[MerkleProof]:
        """Generate Merkle proof for a digest.

        Args:
            digest: Target digest to prove inclusion

        Returns:
            Merkle proof or None if digest not in tree
        """
        if digest not in self.leaves:
            return None

        proof = []
        node = self.leaves[digest]

        while node != self.root:
            parent = self._find_parent(node)
            if not parent:
                break

            if parent.left == node:
                sibling = parent.right
                direction = "right"
            else:
                sibling = parent.left
                direction = "left"

            if sibling:
                proof.append((sibling.digest, direction))
            node = parent

        root_digest = self.root.digest if self.root else ""
        return MerkleProof(
            target_digest=digest,
            proof=proof,
            root_digest=root_digest,
        )

    def _find_parent(self, node: MerkleNode) -> Optional[MerkleNode]:
        """Find parent node in tree.

        Args:
            node: Node to find parent for

        Returns:
            Parent node or None
        """
        def search(current: Optional[MerkleNode]) -> Optional[MerkleNode]:
            if not current or current.is_leaf:
                return None
            if current.left == node or current.right == node:
                return current
            return search(current.left) or search(current.right)

        return search(self.root)

    def verify_proof(self, proof: MerkleProof) -> bool:
        """Verify Merkle proof.

        Args:
            proof: Merkle proof to verify

        Returns:
            True if proof is valid
        """
        current = proof.target_digest

        for sibling, direction in proof.proof:
            if direction == "left":
                current = self._hash_pair(sibling, current)
            else:
                current = self._hash_pair(current, sibling)

        return current == proof.root_digest

    def compute_set_operations(
        self, other_tree: "UORMerkleTree"
    ) -> Dict[str, List[str]]:
        """Compute set operations between two trees.

        Args:
            other_tree: Other Merkle tree to compare with

        Returns:
            Dictionary with union, intersection, difference
        """
        this_digests = set(self.leaves.keys())
        other_digests = set(other_tree.leaves.keys())

        return {
            "union": list(this_digests | other_digests),
            "intersection": list(this_digests & other_digests),
            "difference": list(this_digests - other_digests),
        }
