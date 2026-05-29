"""Digest validation for UOR objects before acceptance.

Provides validation of UOR object digests to ensure content integrity
before accepting objects into the system.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from .bounded_json import compute_uor_digest, canonicalize_json

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of digest validation."""

    is_valid: bool
    expected_digest: Optional[str] = None
    computed_digest: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "expected_digest": self.expected_digest,
            "computed_digest": self.computed_digest,
            "error": self.error,
        }


class DigestValidator:
    """Validates UOR object digests for content integrity."""

    def __init__(self, algorithm: str = "sha256"):
        """Initialize digest validator.

        Args:
            algorithm: Hash algorithm to use for validation
        """
        self.algorithm = algorithm

    def validate_object(
        self, obj: Dict[str, Any], expected_digest: Optional[str] = None
    ) -> ValidationResult:
        """Validate object digest.

        Args:
            obj: Object to validate
            expected_digest: Expected digest (if None, computes and returns)

        Returns:
            ValidationResult with validation outcome
        """
        try:
            computed = compute_uor_digest(obj, algorithm=self.algorithm)

            if expected_digest is None:
                # No expected digest, just compute and return
                return ValidationResult(
                    is_valid=True,
                    expected_digest=None,
                    computed_digest=computed,
                )

            # Compare with expected digest
            if computed == expected_digest:
                return ValidationResult(
                    is_valid=True,
                    expected_digest=expected_digest,
                    computed_digest=computed,
                )
            else:
                logger.warning(
                    "Digest mismatch: expected %s, got %s",
                    expected_digest,
                    computed,
                )
                return ValidationResult(
                    is_valid=False,
                    expected_digest=expected_digest,
                    computed_digest=computed,
                    error="Digest mismatch",
                )
        except Exception:
            logger.exception("Digest validation failed")
            return ValidationResult(
                is_valid=False,
                error="Validation error",
            )

    def validate_envelope(self, envelope: Dict[str, Any]) -> ValidationResult:
        """Validate UOR object envelope digest.

        Args:
            envelope: UOR object envelope with digest field

        Returns:
            ValidationResult with validation outcome
        """
        if "digest" not in envelope:
            return ValidationResult(
                is_valid=False,
                error="Envelope missing digest field",
            )

        expected = envelope["digest"]
        content = envelope.get("content", {})

        # Validate digest matches content
        return self.validate_object(content, expected_digest=expected)

    def validate_canonicalization(
        self, obj: Dict[str, Any], expected_canonical: str
    ) -> ValidationResult:
        """Validate object canonicalization.

        Args:
            obj: Object to validate
            expected_canonical: Expected canonical form

        Returns:
            ValidationResult with validation outcome
        """
        try:
            computed = canonicalize_json(obj)

            if computed == expected_canonical:
                return ValidationResult(
                    is_valid=True,
                    computed_digest=compute_uor_digest(obj),
                )
            else:
                logger.warning("Canonical form mismatch")
                return ValidationResult(
                    is_valid=False,
                    error="Canonical form mismatch",
                )
        except Exception:
            logger.exception("Canonicalization validation failed")
            return ValidationResult(
                is_valid=False,
                error="Validation error",
            )

    def batch_validate(
        self, objects: List[Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate multiple objects.

        Args:
            objects: List of objects to validate

        Returns:
            List of validation results
        """
        results = []
        for obj in objects:
            if "digest" in obj:
                result = self.validate_envelope(obj)
            else:
                result = self.validate_object(obj)
            results.append(result)
        return results


class DigestVerifier:
    """Verifies UOR object digests with cryptographic proofs."""

    def __init__(self, algorithm: str = "sha256"):
        """Initialize digest verifier.

        Args:
            algorithm: Hash algorithm to use
        """
        self.algorithm = algorithm
        self.validator = DigestValidator(algorithm)

    def verify_object_integrity(
        self, obj: Dict[str, Any], trusted_digest: str
    ) -> Tuple[bool, Optional[str]]:
        """Verify object integrity against trusted digest.

        Args:
            obj: Object to verify
            trusted_digest: Trusted digest from authoritative source

        Returns:
            Tuple of (is_valid, error_message)
        """
        result = self.validator.validate_object(obj, trusted_digest)

        if result.is_valid:
            return True, None
        else:
            return False, result.error

    def verify_chain(
        self, objects: List[Dict[str, Any]], chain: List[str]
    ) -> Tuple[bool, List[Tuple[int, str]]]:
        """Verify a chain of object digests.

        Args:
            objects: List of objects in order
            chain: List of expected digests in order

        Returns:
            Tuple of (all_valid, errors)
        """
        errors = []

        if len(objects) != len(chain):
            return False, [
                (
                    0,
                    "Chain length mismatch",
                )
            ]

        for i, (obj, expected) in enumerate(zip(objects, chain)):
            result = self.validator.validate_object(obj, expected)
            if not result.is_valid:
                err_msg = result.error or "Validation failed"
                errors.append((i, err_msg))

        return len(errors) == 0, errors

    def compute_proof(self, obj: Dict[str, Any]) -> Dict[str, str]:
        """Compute cryptographic proof for object.

        Args:
            obj: Object to compute proof for

        Returns:
            Dictionary with digest and canonical form
        """
        digest = compute_uor_digest(obj, algorithm=self.algorithm)
        canonical = canonicalize_json(obj)

        return {
            "digest": digest,
            "canonical": canonical,
            "algorithm": self.algorithm,
        }
