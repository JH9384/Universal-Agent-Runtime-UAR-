"""Tests for uar.uor.identity."""

from uar.uor.identity import (
    UORIdentityVerifier,
    bnot,
    compute_identity_chain,
    neg,
    succ,
    verify_critical_identity,
)


class TestRingOperations:
    def test_bnot(self):
        assert bnot(42, 8) == 213

    def test_neg(self):
        assert neg(42, 8) == 214

    def test_succ(self):
        assert succ(42, 8) == 43


class TestVerifyCriticalIdentity:
    def test_n8(self):
        assert verify_critical_identity(8) is True

    def test_n4(self):
        assert verify_critical_identity(4) is True


class TestComputeIdentityChain:
    def test_chain(self):
        chain = compute_identity_chain(42, 8)
        assert chain["x"] == 42
        assert chain["bnot"] == 213
        assert chain["neg_bnot"] == 43
        assert chain["succ"] == 43
        assert chain["valid"] is True


class TestUORIdentityVerifier:
    def test_init(self):
        v = UORIdentityVerifier(n=8)
        assert v.n == 8
        assert v.mod == 256

    def test_verify_object_identity(self):
        v = UORIdentityVerifier(n=8)
        assert v.verify_object_identity("sha256:abc", 42) is True

    def test_compute_ring_value(self):
        v = UORIdentityVerifier(n=8)
        assert v.compute_ring_value(300) == 44
