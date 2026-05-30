"""Tests for uar.uor.merkle."""

import pytest

from uar.uor.merkle import UORMerkleTree


class TestUORMerkleTree:
    def test_sha3_256(self):
        tree = UORMerkleTree(hash_algorithm="sha3-256")
        digests = ["a", "b"]
        tree.build_tree(digests)
        assert tree.get_root_digest() is not None

    def test_unsupported_hash(self):
        tree = UORMerkleTree(hash_algorithm="md5")
        with pytest.raises(ValueError, match="Unsupported"):
            tree._hash(b"data")

    def test_build_tree_empty(self):
        tree = UORMerkleTree()
        with pytest.raises(ValueError, match="empty"):
            tree.build_tree([])

    def test_get_root_digest_none(self):
        tree = UORMerkleTree()
        assert tree.get_root_digest() is None

    def test_generate_proof_not_found(self):
        tree = UORMerkleTree()
        tree.build_tree(["a", "b"])
        assert tree.generate_proof("z") is None

    def test_verify_proof_left_direction(self):
        tree = UORMerkleTree()
        digests = ["a", "b", "c", "d"]
        tree.build_tree(digests)
        proof = tree.generate_proof("c")
        assert proof is not None
        # c is left child, so first proof step should be "left" direction
        assert any(direction == "left" for _, direction in proof.proof)
        assert tree.verify_proof(proof)

    def test_compute_set_operations(self):
        tree1 = UORMerkleTree()
        tree1.build_tree(["a", "b"])
        tree2 = UORMerkleTree()
        tree2.build_tree(["b", "c"])
        result = tree1.compute_set_operations(tree2)
        assert set(result["union"]) == {"a", "b", "c"}
        assert set(result["intersection"]) == {"b"}
        assert set(result["difference"]) == {"a"}
