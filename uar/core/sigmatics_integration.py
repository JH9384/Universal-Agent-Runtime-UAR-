"""Sigmatics Integration Layer for UAR.

This module provides Python integration with the UOR Foundation's
Sigmatics (Atlas Sigil Algebra) reference implementation.

Sigmatics provides:
- Atlas Sigil Algebra for mathematical operations
- Symbolic computation capabilities
- Integration with UOR object references

Since Sigmatics is an npm package (JavaScript/TypeScript), this module
provides a Python interface that can either:
1. Call the Sigmatics CLI via subprocess (if installed globally)
2. Provide Python-native implementations of key Sigmatics concepts
3. Serve as a bridge for future native Python bindings
"""

import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import subprocess
import json

from .uor_integration import UORObject, ObjectMode

logger = logging.getLogger(__name__)


@dataclass
class Sigil:
    """Represents a sigil in the Atlas Sigil Algebra."""

    symbol: str
    value: Optional[Union[int, float, str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert sigil to dictionary representation."""
        return {
            "symbol": self.symbol,
            "value": self.value,
            "metadata": self.metadata,
        }


@dataclass
class SigilExpression:
    """Represents a sigil expression/computation."""

    sigils: List[Sigil]
    operation: str
    result: Optional[Any] = None
    uor_object: Optional[UORObject] = None

    def evaluate(self) -> Any:
        """Evaluate the sigil expression."""
        # This is a placeholder for actual sigil algebra evaluation
        # In a full implementation, this would use the Sigmatics library
        if self.operation == "sum":
            values = [
                s.value
                for s in self.sigils
                if isinstance(s.value, (int, float))
            ]
            self.result = sum(values)
        elif self.operation == "product":
            values = [
                s.value
                for s in self.sigils
                if isinstance(s.value, (int, float))
            ]
            self.result = 1
            for v in values:
                self.result *= v
        else:
            self.result = None

        return self.result

    def wrap_with_uor(self, source: str = "sigmatics") -> UORObject:
        """Wrap the expression result in a UOR object."""
        if self.result is None:
            self.evaluate()

        uor_obj = UORObject(
            data=self.result, mode=ObjectMode.IMMUTABLE_SINGULAR
        )
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "sigil_expression")
        uor_obj.add_schema_extension("sigil_operation", self.operation)
        uor_obj.add_schema_extension("sigil_count", len(self.sigils))

        self.uor_object = uor_obj
        return uor_obj


class SigmaticsIntegrator:
    """Main Sigmatics integration coordinator for UAR."""

    def __init__(self, use_cli: bool = False):
        """
        Initialize Sigmatics integrator.

        Args:
            use_cli: If True, attempt to use Sigmatics CLI via subprocess.
                    If False, use Python-native implementations.
        """
        self.use_cli = use_cli
        self.cli_available = False
        self.expression_cache: Dict[str, SigilExpression] = {}

        if self.use_cli:
            self.cli_available = self._check_cli_availability()

    def _check_cli_availability(self) -> bool:
        """Check if Sigmatics CLI is available."""
        try:
            result = subprocess.run(
                ["sigmatics", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning(
                "Sigmatics CLI not found. Using Python-native implementations."
            )
            return False

    def create_sigil(
        self,
        symbol: str,
        value: Optional[Union[int, float, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Sigil:
        """Create a sigil object."""
        return Sigil(symbol=symbol, value=value, metadata=metadata)

    def create_expression(
        self, sigils: List[Sigil], operation: str
    ) -> SigilExpression:
        """Create a sigil expression."""
        expr = SigilExpression(sigils=sigils, operation=operation)
        expr_id = self._generate_expression_id(expr)
        self.expression_cache[expr_id] = expr
        return expr

    def _generate_expression_id(self, expr: SigilExpression) -> str:
        """Generate a unique ID for a sigil expression."""
        symbols = "-".join([s.symbol for s in expr.sigils])
        return f"{expr.operation}:{symbols}"

    def evaluate_via_cli(
        self, expression_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Evaluate a sigil expression using the Sigmatics CLI.

        Args:
            expression_data: Dictionary representation of the expression

        Returns:
            Evaluation result or None if CLI unavailable
        """
        if not self.cli_available:
            logger.warning("Sigmatics CLI not available")
            return None

        try:
            result = subprocess.run(
                ["sigmatics", "evaluate", json.dumps(expression_data)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Sigmatics CLI error: {result.stderr}")
                return None

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error(f"Sigmatics CLI evaluation failed: {e}")
            return None

    def integrate_with_uor(
        self, sigil_expr: SigilExpression, source: str = "sigmatics"
    ) -> UORObject:
        """Integrate sigil expression with UOR system."""
        uor_obj = sigil_expr.wrap_with_uor(source)

        # Add schema extensions for sigil algebra tracking
        uor_obj.add_schema_extension("sigil_algebra", True)
        uor_obj.add_schema_extension(
            "sigil_symbols", [s.symbol for s in sigil_expr.sigils]
        )

        return uor_obj

    def batch_process_sigils(
        self, sigil_list: List[Sigil], operation: str = "sum"
    ) -> List[UORObject]:
        """Process multiple sigils and return UOR objects."""
        results = []

        # Create expression
        expr = self.create_expression(sigil_list, operation)

        # Integrate with UOR
        uor_obj = self.integrate_with_uor(expr)
        results.append(uor_obj)

        return results


# Global Sigmatics integrator instance
_sigmatics_integrator: Optional[SigmaticsIntegrator] = None


def get_sigmatics_integrator() -> SigmaticsIntegrator:
    """Get the global Sigmatics integrator instance."""
    global _sigmatics_integrator
    if _sigmatics_integrator is None:
        _sigmatics_integrator = SigmaticsIntegrator()
    return _sigmatics_integrator


def reset_sigmatics_integrator():
    """Reset the global Sigmatics integrator (useful for testing)."""
    global _sigmatics_integrator
    _sigmatics_integrator = None


def create_sigil(
    symbol: str,
    value: Optional[Union[int, float, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Sigil:
    """Convenience function to create a sigil."""
    integrator = get_sigmatics_integrator()
    return integrator.create_sigil(symbol, value, metadata)


def create_sigil_expression(
    sigils: List[Sigil], operation: str
) -> SigilExpression:
    """Convenience function to create a sigil expression."""
    integrator = get_sigmatics_integrator()
    return integrator.create_expression(sigils, operation)
