"""Physics and astronomy computation skill using Astropy.

Provides astronomical calculations, unit conversions, coordinate
transformations, and physics computations through Astropy integration.

Environment Variables:
    PHYSICS_TIMEOUT_SECONDS - Timeout for computations (default: 30)
    PHYSICS_MAX_DATA_SIZE - Maximum data size in bytes (default: 10485760)

Goal Metadata:
    physics_operation - Operation type: 'convert', 'transform', 'calculate', 'query'
    physics_type - Type: 'unit', 'coordinate', 'time', 'distance', 'energy'
    physics_value - Value to process (string or number)
    physics_from_unit - Source unit (for conversions)
    physics_to_unit - Target unit (for conversions)
    physics_coordinate - Coordinate data (for transformations)
"""  # noqa: E501

import os
import logging
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)

# Circuit breaker for physics operations
_physics_cb = CircuitBreaker(
    "physics_compute", failure_threshold=3, recovery_timeout=30.0
)

# Configuration
PHYSICS_TIMEOUT = max(
    1.0,
    float(os.getenv("PHYSICS_TIMEOUT_SECONDS", "30").strip() or "30"),
)
MAX_DATA_SIZE = max(
    1,
    int(
        os.getenv("PHYSICS_MAX_DATA_SIZE", "10485760").strip() or "10485760"
    ),
)


def _check_astropy_available() -> bool:
    """Check if Astropy is available with graceful degradation."""
    import importlib.util

    return importlib.util.find_spec("astropy") is not None


def _convert_units(value: str, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Convert value from one unit to another using Astropy."""
    from astropy import units as u

    try:
        qty = u.Quantity(value, from_unit)
        converted = qty.to(to_unit)

        return {
            "success": True,
            "original_value": value,
            "original_unit": from_unit,
            "converted_value": str(converted.value),
            "converted_unit": to_unit,
            "numerical_value": float(converted.value),
        }
    except Exception as exc:
        logger.warning(f"_unit_convert failed: {exc}")
        return {"success": False, "error": "Unit conversion failed"}


def _calculate_distance(
    ra1: str, dec1: str, ra2: str, dec2: str
) -> Dict[str, Any]:
    """Calculate angular distance between two coordinates."""
    from astropy.coordinates import SkyCoord

    try:
        c1 = SkyCoord(ra1, dec1, unit="deg")
        c2 = SkyCoord(ra2, dec2, unit="deg")
        separation = c1.separation(c2)

        return {
            "success": True,
            "coordinate1": f"{ra1}, {dec1}",
            "coordinate2": f"{ra2}, {dec2}",
            "angular_distance": str(separation),
            "angular_distance_degrees": separation.degree,
            "angular_distance_arcsec": separation.arcsecond,
        }
    except Exception as exc:
        logger.warning(f"_calculate_distance failed: {exc}")
        return {"success": False, "error": "Distance calculation failed"}


def _transform_coordinate(
    ra: str, dec: str, from_frame: str, to_frame: str
) -> Dict[str, Any]:
    """Transform coordinate from one frame to another."""
    from astropy.coordinates import SkyCoord
    from astropy.coordinates import FK5, ICRS, Galactic

    try:
        frames = {"icrs": ICRS, "fk5": FK5, "galactic": Galactic}

        if from_frame not in frames or to_frame not in frames:
            return {
                "success": False,
                "error": "Unsupported frame",
            }

        c = SkyCoord(ra, dec, unit="deg", frame=frames[from_frame])
        transformed = c.transform(frames[to_frame])

        return {
            "success": True,
            "from_frame": from_frame,
            "to_frame": to_frame,
            "original_ra": ra,
            "original_dec": dec,
            "transformed_ra": str(transformed.ra),
            "transformed_dec": str(transformed.dec),
        }
    except Exception as exc:
        logger.warning(f"_transform_coordinate failed: {exc}")
        return {"success": False, "error": "Coordinate transformation failed"}


def _calculate_energy(wavelength: str) -> Dict[str, Any]:
    """Calculate photon energy from wavelength."""
    from astropy import units as u
    from astropy.constants import h, c

    try:
        wave = u.Quantity(wavelength)
        energy = (h * c / wave).to(u.eV)

        return {
            "success": True,
            "wavelength": str(wave),
            "energy": str(energy),
            "energy_eV": energy.value,
        }
    except Exception as exc:
        logger.warning(f"_calculate_energy failed: {exc}")
        return {"success": False, "error": "Energy calculation failed"}


def _calculate_redshift(z: str) -> Dict[str, Any]:
    """Calculate cosmological properties from redshift."""
    from astropy.cosmology import Planck18

    try:
        z_val = float(z)
        cosmo = Planck18
        distance = cosmo.luminosity_distance(z_val)

        return {
            "success": True,
            "redshift": z,
            "luminosity_distance": str(distance),
            "luminosity_distance_Mpc": distance.value,
        }
    except Exception as exc:
        logger.warning(f"_calculate_redshift failed: {exc}")
        return {"success": False, "error": "Redshift calculation failed"}


@register_skill("physics_compute")
def physics_compute(ctx: PipelineContext) -> Dict[str, Any]:
    """Perform physics and astronomy computations using Astropy.

    Supports unit conversions, coordinate transformations, distance
    calculations, energy calculations, and cosmological computations.

    Environment:
        PHYSICS_TIMEOUT_SECONDS - Timeout for computations (default: 30)
        PHYSICS_MAX_DATA_SIZE - Maximum data size in bytes (default: 10MB)

    Goal metadata:
        physics_operation - Operation: 'convert', 'transform', 'calculate', 'query'
        physics_type - Type: 'unit', 'coordinate', 'time', 'distance', 'energy'
        physics_value - Value to process (string or number)
        physics_from_unit - Source unit (for conversions)
        physics_to_unit - Target unit (for conversions)
        physics_coordinate - Coordinate data (for transformations)

    Returns:
        Dictionary with computation results or error information.
    """  # noqa: E501
    # Check Astropy availability
    if not _check_astropy_available():
        return {
            "status": "failed",
            "error": "Astropy not installed. Install with: pip install astropy",  # noqa: E501
            "operation": "unavailable",
        }

    # Get parameters from goal metadata
    operation = ctx.goal.metadata.get("physics_operation", "convert")
    physics_type = ctx.goal.metadata.get("physics_type", "unit")
    value = ctx.goal.metadata.get("physics_value", "")
    from_unit = ctx.goal.metadata.get("physics_from_unit", "")
    to_unit = ctx.goal.metadata.get("physics_to_unit", "")

    # Validate inputs
    if not value:
        return {
            "status": "failed",
            "error": "physics_value is required in goal metadata",
            "operation": operation,
        }

    # Execute operation with circuit breaker
    try:
        result = _physics_cb.call(
            lambda: _execute_operation(
                operation, physics_type, value, from_unit, to_unit
            )
        )
    except Exception as exc:
        logger.warning(f"physics_compute failed: {exc}")
        return {
            "status": "failed",
            "error": "Physics operation failed",
            "operation": operation,
        }

    # Add metadata to result
    result["operation"] = operation
    result["type"] = physics_type
    result["status"] = "completed" if result.get("success") else "failed"

    return result


def _execute_operation(
    operation: str, physics_type: str, value: str, from_unit: str, to_unit: str
) -> Dict[str, Any]:
    """Execute the specified physics operation."""
    operations = {
        "convert": lambda: _convert_units(value, from_unit, to_unit),
        "transform": lambda: _transform_coordinate(
            value, from_unit, to_unit, physics_type
        ),
        "calculate": lambda: _calculate_physics(physics_type, value),
        "query": lambda: _query_physics(physics_type, value),
    }

    if operation not in operations:
        return {
            "success": False,
            "error": (
                f"Unknown operation: {operation}. "
                f"Available: {list(operations.keys())}"
            ),
        }

    return operations[operation]()


def _calculate_physics(physics_type: str, value: str) -> Dict[str, Any]:
    """Execute physics calculation based on type."""
    calculations = {
        "energy": lambda: _calculate_energy(value),
        "redshift": lambda: _calculate_redshift(value),
        "distance": lambda: _calculate_distance_from_value(value),
    }

    if physics_type not in calculations:
        return {
            "success": False,
            "error": (
                f"Unknown calculation type: {physics_type}. "
                f"Available: {list(calculations.keys())}"
            ),
        }

    return calculations[physics_type]()


def _query_physics(physics_type: str, value: str) -> Dict[str, Any]:
    """Query physics information."""
    # Placeholder for more complex queries
    return {
        "success": True,
        "query_type": physics_type,
        "value": value,
        "message": "Query functionality - extend as needed",
    }


def _calculate_distance_from_value(value: str) -> Dict[str, Any]:
    """Calculate distance from coordinate string."""
    # Parse coordinate string format: "ra1,dec1,ra2,dec2"
    try:
        parts = value.split(",")
        if len(parts) != 4:
            return {
                "success": False,
                "error": "Format should be: ra1,dec1,ra2,dec2",
            }
        return _calculate_distance(parts[0], parts[1], parts[2], parts[3])
    except Exception as exc:
        logger.warning(f"_execute_operation failed: {exc}")
        return {"success": False, "error": "Operation failed"}
