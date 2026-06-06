"""UOR critical identity operations.

Implements the UOR critical identity: neg(bnot(42)) = succ(42) in R_8 ring.
These operations are fundamental to UOR's mathematical foundations and provide
object integrity verification capabilities.

Reference: UOR Foundation public surface documentation
"""

import logging
from typing import Union

logger = logging.getLogger(__name__)


def bnot(x: int, n: int = 8) -> int:
    """Bitwise NOT in n-bit ring R_n = Z/(2^n)Z.

    Args:
        x: Integer value
        n: Ring size in bits (default 8 for R_8)

    Returns:
        Bitwise NOT of x in n-bit ring

    Example:
        >>> bnot(42, 8)
        213
        # In R_8: bnot(42) = 42 XOR 255 = 213
    """
    mask = (1 << n) - 1
    return x ^ mask


def neg(x: int, n: int = 8) -> int:
    """Negation in n-bit ring R_n = Z/(2^n)Z.

    Args:
        x: Integer value
        n: Ring size in bits (default 8 for R_8)

    Returns:
        Negation of x in n-bit ring

    Example:
        >>> neg(42, 8)
        214
        # In R_8: neg(42) = (-42) mod 256 = 214
    """
    mod = 1 << n
    return (-x) % mod


def succ(x: int, n: int = 8) -> int:
    """Successor in n-bit ring R_n = Z/(2^n)Z.

    Args:
        x: Integer value
        n: Ring size in bits (default 8 for R_8)

    Returns:
        Successor of x in n-bit ring

    Example:
        >>> succ(42, 8)
        43
        # In R_8: succ(42) = (42 + 1) mod 256 = 43
    """
    mod = 1 << n
    return (x + 1) % mod


def verify_critical_identity(n: int = 8) -> bool:
    """Verify the UOR critical identity: neg(bnot(x)) = succ(x) in R_n.

    This is the public quick verification identity from UOR Foundation.

    Args:
        n: Ring size in bits (default 8 for R_8)

    Returns:
        True if identity holds for all values in R_n

    Example:
        >>> verify_critical_identity(8)
        True
        # For x=42 in R_8: bnot(42) = 213, neg(213) = 43, succ(42) = 43
        # neg(bnot(42)) == succ(42) ✓
    """
    mod = 1 << n
    for x in range(mod):
        lhs = neg(bnot(x, n), n)
        rhs = succ(x, n)
        if lhs != rhs:  # pragma: no cover
            err_msg = (
                f"Identity failed for x={x}: neg(bnot({x}))={lhs} "
                f"!= succ({x})={rhs}"
            )
            logger.error(err_msg)
            return False
    return True


def compute_identity_chain(x: int, n: int = 8) -> dict:
    """Compute the full identity chain for a value in R_n.

    Args:
        x: Integer value
        n: Ring size in bits (default 8 for R_8)

    Returns:
        Dictionary with all intermediate values

    Example:
        >>> compute_identity_chain(42, 8)
        {'x': 42, 'bnot': 213, 'neg_bnot': 43, 'succ': 43, 'valid': True}
    """
    x_bnot = bnot(x, n)
    x_neg_bnot = neg(x_bnot, n)
    x_succ = succ(x, n)
    valid = x_neg_bnot == x_succ

    return {
        "x": x,
        "bnot": x_bnot,
        "neg_bnot": x_neg_bnot,
        "succ": x_succ,
        "valid": valid,
    }


class UORIdentityVerifier:
    """Verifier for UOR identity-based object integrity checks."""

    def __init__(self, n: int = 8):
        """Initialize verifier with ring size.

        Args:
            n: Ring size in bits (default 8 for R_8)
        """
        self.n = n
        self.mod = 1 << n

    def verify_object_identity(
        self, digest: str, expected: Union[int, str]
    ) -> bool:
        """Verify object identity using digest-based operations.

        Derives a ring value from the trailing hex digits of *digest*,
        then verifies the UOR critical identity
        ``neg(bnot(x)) == succ(x)`` in :math:`R_{self.n}`.

        Args:
            digest: UOR digest string (e.g., "sha256:<hex>")
            expected: Expected identity value (int or hex string)

        Returns:
            True if identity verification passes
        """
        # Extract a stable ring value from the digest
        hex_part = digest.split(":")[-1] if ":" in digest else digest
        if not hex_part:
            logger.warning("Empty digest provided for identity verification")
            return False

        # Use the last 8 hex digits as a 32-bit seed, then map into R_n
        try:
            seed = int(hex_part[-8:], 16)
        except ValueError:
            logger.warning("Digest contains non-hex characters: %s", digest)
            return False

        x = seed % self.mod

        # Verify the critical identity: neg(bnot(x)) == succ(x)
        lhs = neg(bnot(x, self.n), self.n)
        rhs = succ(x, self.n)
        valid = lhs == rhs

        if not valid:
            logger.error(
                "Critical identity failed for digest %s: "
                "neg(bnot(%s))=%s != succ(%s)=%s",
                digest,
                x,
                lhs,
                x,
                rhs,
            )
            return False

        # Compare against expected value if provided
        if expected is not None:
            expected_int = (
                int(expected, 16)
                if isinstance(expected, str)
                else int(expected)
            )
            if x != expected_int % self.mod:
                logger.warning(
                    "Digest-derived value %s does not match expected %s",
                    x,
                    expected_int % self.mod,
                )
                return False

        logger.debug(
            "Identity verified for digest %s: x=%s, neg(bnot(x))=%s, "
            "succ(x)=%s",
            digest,
            x,
            lhs,
            rhs,
        )
        return True

    def compute_ring_value(self, value: int) -> int:
        """Compute value in ring R_n.

        Args:
            value: Integer value to reduce to ring

        Returns:
            Value modulo 2^n
        """
        return value % self.mod
