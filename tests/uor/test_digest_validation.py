"""Tests for UOR object digest validation.

Covers DigestValidator, DigestVerifier, ValidationResult.
"""

from unittest.mock import patch

from uar.uor.digest_validation import (
    ValidationResult,
    DigestValidator,
    DigestVerifier,
)


class TestValidationResult:
    """ValidationResult dataclass."""

    def test_to_dict(self):
        r = ValidationResult(
            is_valid=True,
            expected_digest="sha256:abc",
            computed_digest="sha256:abc",
            error=None,
        )
        d = r.to_dict()
        assert d["is_valid"] is True
        assert d["expected_digest"] == "sha256:abc"
        assert d["computed_digest"] == "sha256:abc"
        assert d["error"] is None

    def test_defaults(self):
        r = ValidationResult(is_valid=False)
        assert r.expected_digest is None
        assert r.computed_digest is None
        assert r.error is None


class TestDigestValidatorValidateObject:
    """Single object digest validation."""

    def test_no_expected_digest(self):
        v = DigestValidator()
        obj = {"hello": "world"}
        result = v.validate_object(obj)
        assert result.is_valid is True
        assert result.expected_digest is None
        assert result.computed_digest is not None
        assert result.error is None

    def test_matching_digest(self):
        v = DigestValidator()
        obj = {"hello": "world"}
        computed = v.validate_object(obj).computed_digest
        result = v.validate_object(obj, expected_digest=computed)
        assert result.is_valid is True
        assert result.computed_digest == computed

    def test_mismatch_digest(self):
        v = DigestValidator()
        obj = {"hello": "world"}
        result = v.validate_object(obj, expected_digest="wrong")
        assert result.is_valid is False
        assert result.error == "Digest mismatch"
        assert result.computed_digest is not None

    def test_validation_error(self):
        v = DigestValidator()
        with patch(
            "uar.uor.digest_validation.compute_uor_digest",
            side_effect=ValueError("boom"),
        ):
            result = v.validate_object({})
        assert result.is_valid is False
        assert result.error == "Validation error"


class TestDigestValidatorValidateEnvelope:
    """Envelope validation."""

    def test_missing_digest_field(self):
        v = DigestValidator()
        result = v.validate_envelope({"content": {}})
        assert result.is_valid is False
        assert "missing digest" in result.error.lower()

    def test_valid_envelope(self):
        v = DigestValidator()
        obj = {"hello": "world"}
        digest = v.validate_object(obj).computed_digest
        envelope = {"content": obj, "digest": digest}
        result = v.validate_envelope(envelope)
        assert result.is_valid is True

    def test_invalid_envelope(self):
        v = DigestValidator()
        envelope = {"content": {"hello": "world"}, "digest": "wrong"}
        result = v.validate_envelope(envelope)
        assert result.is_valid is False
        assert result.error == "Digest mismatch"


class TestDigestValidatorValidateCanonicalization:
    """Canonical form validation."""

    def test_matching_canonical(self):
        v = DigestValidator()
        obj = {"b": 2, "a": 1}
        from uar.uor.bounded_json import canonicalize_json

        expected = canonicalize_json(obj)
        result = v.validate_canonicalization(obj, expected)
        assert result.is_valid is True
        assert result.computed_digest is not None

    def test_mismatch_canonical(self):
        v = DigestValidator()
        result = v.validate_canonicalization({"a": 1}, "wrong")
        assert result.is_valid is False
        assert result.error == "Canonical form mismatch"

    def test_canonicalization_error(self):
        v = DigestValidator()
        with patch(
            "uar.uor.digest_validation.canonicalize_json",
            side_effect=ValueError("boom"),
        ):
            result = v.validate_canonicalization({}, "x")
        assert result.is_valid is False
        assert result.error == "Validation error"


class TestDigestValidatorBatchValidate:
    """Batch validation."""

    def test_mixed_objects(self):
        v = DigestValidator()
        obj = {"hello": "world"}
        digest = v.validate_object(obj).computed_digest
        objects = [
            obj,
            {"digest": digest, "content": obj},
            {"no": "digest"},
        ]
        results = v.batch_validate(objects)
        assert len(results) == 3
        assert all(r.computed_digest is not None for r in results)


class TestDigestVerifier:
    """DigestVerifier high-level API."""

    def test_verify_object_integrity_valid(self):
        v = DigestVerifier()
        obj = {"hello": "world"}
        digest = v.validator.validate_object(obj).computed_digest
        valid, err = v.verify_object_integrity(obj, digest)
        assert valid is True
        assert err is None

    def test_verify_object_integrity_invalid(self):
        v = DigestVerifier()
        obj = {"hello": "world"}
        valid, err = v.verify_object_integrity(obj, "wrong")
        assert valid is False
        assert err is not None

    def test_verify_chain_success(self):
        v = DigestVerifier()
        obj1 = {"a": 1}
        obj2 = {"b": 2}
        d1 = v.validator.validate_object(obj1).computed_digest
        d2 = v.validator.validate_object(obj2).computed_digest
        valid, errors = v.verify_chain([obj1, obj2], [d1, d2])
        assert valid is True
        assert errors == []

    def test_verify_chain_length_mismatch(self):
        v = DigestVerifier()
        valid, errors = v.verify_chain([{"a": 1}], [])
        assert valid is False
        assert len(errors) == 1
        assert "length mismatch" in errors[0][1].lower()

    def test_verify_chain_digest_mismatch(self):
        v = DigestVerifier()
        obj = {"a": 1}
        valid, errors = v.verify_chain([obj], ["wrong"])
        assert valid is False
        assert len(errors) == 1

    def test_compute_proof(self):
        v = DigestVerifier()
        obj = {"hello": "world"}
        proof = v.compute_proof(obj)
        assert "digest" in proof
        assert "canonical" in proof
        assert proof["algorithm"] == "sha256"
