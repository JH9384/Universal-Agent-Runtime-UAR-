"""UOR Helper Utilities for UAR.

This module provides helper utilities and convenience functions
for working with UOR integrations across the UAR system.
"""

import logging
from typing import Any, Dict, List

from .uor_integration import (
    UORObject,
    ObjectMode,
    wrap_input_data,
    get_uor_integrator,
)
from .sigmatics_integration import (
    Sigil,
    get_sigmatics_integrator,
)
from .atlas_embeddings import get_atlas_integrator
from .ego_guard_forge import get_ego_guard_integrator
from .prism_integration import get_prism_integrator
from .uor_ecosystem import get_uor_ecosystem

logger = logging.getLogger(__name__)


class UORHelper:
    """Unified helper class for UOR operations."""

    @staticmethod
    def wrap_data_with_uor(
        data: Any,
        source: str = "unknown",
        mode: ObjectMode = ObjectMode.IMMUTABLE_SINGULAR,
    ) -> UORObject:
        """Wrap data with UOR object."""
        uor_obj = UORObject(data=data, mode=mode)
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "wrap")
        return uor_obj

    @staticmethod
    def verify_uor_chain(
        uor_obj: UORObject, expected_sources: List[str]
    ) -> bool:
        """Verify that UOR object has expected provenance sources."""
        actual_sources = [p["source"] for p in uor_obj.provenance]
        return all(source in actual_sources for source in expected_sources)

    @staticmethod
    def get_uor_summary(uor_obj: UORObject) -> Dict[str, Any]:
        """Get a summary of UOR object information."""
        return {
            "digest": uor_obj.digest,
            "size": uor_obj.size,
            "media_type": uor_obj.media_type,
            "mode": uor_obj.mode.value,
            "provenance_count": len(uor_obj.provenance),
            "transformation_count": len(uor_obj.transformations),
            "schema_extensions_count": len(uor_obj.schema_extensions),
        }


class UORAssetHelper:
    """Helper for UOR Foundation assets."""

    @staticmethod
    def create_computation_pipeline(
        data: Any,
        apply_sigil: bool = False,
        apply_embedding: bool = False,
        apply_security: bool = False,
        apply_prism: bool = False,
    ) -> Dict[str, Any]:
        """Create a computation pipeline using UOR assets."""
        results: Dict[str, Any] = {}

        # Wrap input with UOR
        input_uor = wrap_input_data(data, source="pipeline")
        results["input_digest"] = input_uor.digest

        # Sigmatics
        if apply_sigil:
            sig_int = get_sigmatics_integrator()
            sigil_list = [
                Sigil("x", value=data)
                if isinstance(data, (int, float))
                else Sigil("x")
            ]
            sigil_expr = sig_int.create_expression(sigil_list, "sum")
            sigil_uor = sig_int.integrate_with_uor(sigil_expr)
            results["sigil_digest"] = sigil_uor.digest

        # Atlas Embeddings
        if apply_embedding:
            atlas_int = get_atlas_integrator()
            seed = atlas_int.create_golden_seed(random=True)
            embedding_uor = atlas_int.integrate_with_uor(seed)
            results["embedding_digest"] = embedding_uor.digest

        # Ego Guard Forge
        if apply_security:
            guard_int = get_ego_guard_integrator()
            policy = guard_int.create_policy(
                policy_id="pipeline_policy",
                name="Pipeline Security",
                description="Security for pipeline",
                rules={"enabled": True},
            )
            policy_uor = guard_int.integrate_with_uor(policy)
            results["policy_digest"] = policy_uor.digest

        # Prism
        if apply_prism:
            prism_int = get_prism_integrator()
            prism = prism_int.create_prism("pipeline_prism")
            prism_uor = prism_int.integrate_with_uor(prism)
            results["prism_digest"] = prism_uor.digest

        # UOR Ecosystem
        eco = get_uor_ecosystem()
        eco_status = eco.status()
        results["ecosystem"] = eco_status

        return results

    @staticmethod
    def get_ecosystem_status() -> Dict[str, Any]:
        """Return status of all UOR ecosystem integrations."""
        return get_uor_ecosystem().status()

    @staticmethod
    def reset_all_integrators():
        """Reset all UOR integrators (useful for testing)."""
        from .uor_integration import reset_uor_integrator
        from .sigmatics_integration import reset_sigmatics_integrator
        from .atlas_embeddings import reset_atlas_integrator
        from .ego_guard_forge import reset_ego_guard_integrator
        from .prism_integration import reset_prism_integrator
        from .uor_ecosystem import reset_uor_ecosystem

        reset_uor_integrator()
        reset_sigmatics_integrator()
        reset_atlas_integrator()
        reset_ego_guard_integrator()
        reset_prism_integrator()
        reset_uor_ecosystem()

        logger.info("All UOR integrators reset")


class UORMetricsHelper:
    """Helper for collecting UOR metrics."""

    @staticmethod
    def collect_uor_metrics() -> Dict[str, Any]:
        """Collect metrics from all UOR integrators."""
        metrics = {}

        # UOR Integration
        uor_int = get_uor_integrator()
        metrics["uor_integration"] = {
            "enabled": uor_int.enabled,
            "object_cache_size": len(uor_int.object_cache),
            "digest_history_size": len(uor_int.digest_history),
        }

        # Sigmatics
        sig_int = get_sigmatics_integrator()
        metrics["sigmatics"] = {
            "cli_available": sig_int.cli_available,
            "expression_cache_size": len(sig_int.expression_cache),
        }

        # Atlas Embeddings
        atlas_int = get_atlas_integrator()
        metrics["atlas_embeddings"] = {
            "enabled": atlas_int.enabled,
            "vector_cache_size": len(atlas_int.vector_cache),
        }

        # Ego Guard Forge
        guard_int = get_ego_guard_integrator()
        metrics["ego_guard_forge"] = {
            "enabled": guard_int.enabled,
            "policy_count": len(guard_int.policies),
            "audit_trail_size": len(guard_int.audit_trail),
        }

        # Prism
        prism_int = get_prism_integrator()
        metrics["prism"] = {
            "enabled": prism_int.enabled,
            "prism_count": len(prism_int.prisms),
        }

        return metrics

    @staticmethod
    def get_uor_health_status() -> Dict[str, str]:
        """Get health status of all UOR integrators."""
        status = {}

        metrics = UORMetricsHelper.collect_uor_metrics()

        for component, comp_metrics in metrics.items():
            if comp_metrics.get("enabled", False):
                status[component] = "healthy"
            else:
                status[component] = "disabled"

        return status


class UORValidationHelper:
    """Helper for UOR validation operations."""

    @staticmethod
    def validate_uor_object(uor_obj: UORObject) -> Dict[str, Any]:
        """Validate a UOR object."""
        validation: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        # Check digest
        if uor_obj.digest is None:
            validation["valid"] = False
            validation["errors"].append("Digest is None")

        # Check size
        if uor_obj.size is None:
            validation["warnings"].append("Size is None")

        # Check media type
        if uor_obj.media_type is None:
            validation["warnings"].append("Media type is None")

        # Check provenance
        if not uor_obj.provenance:
            validation["warnings"].append("No provenance records")

        return validation

    @staticmethod
    def validate_uor_chain(uor_objects: List[UORObject]) -> Dict[str, Any]:
        """Validate a chain of UOR objects."""
        validation: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "chain_breaks": [],
        }

        for i, uor_obj in enumerate(uor_objects):
            obj_validation = UORValidationHelper.validate_uor_object(uor_obj)

            if not obj_validation["valid"]:
                validation["valid"] = False
                validation["errors"].extend(
                    [f"Object {i}: {e}" for e in obj_validation["errors"]]
                )

            validation["warnings"].extend(
                [f"Object {i}: {w}" for w in obj_validation["warnings"]]
            )

            # Check chain continuity
            if i > 0 and uor_objects[i - 1].digest not in [
                p.get("digest") for p in uor_obj.provenance
            ]:
                validation["chain_breaks"].append(f"Break at index {i}")

        return validation


# Convenience functions for common operations


def wrap_and_track(data: Any, source: str) -> UORObject:
    """Wrap data with UOR and track provenance."""
    return UORHelper.wrap_data_with_uor(data, source)


def get_all_uor_digests() -> Dict[str, List[str]]:
    """Get all UOR digests from integrators."""
    digests = {}

    uor_int = get_uor_integrator()
    digests["uor_integration"] = list(uor_int.object_cache.keys())

    atlas_int = get_atlas_integrator()
    digests["atlas_embeddings"] = list(atlas_int.vector_cache.keys())

    sig_int = get_sigmatics_integrator()
    digests["sigmatics"] = list(sig_int.expression_cache.keys())

    return digests


def clear_uor_caches():
    """Clear all UOR caches."""
    uor_int = get_uor_integrator()
    uor_int.object_cache.clear()
    uor_int.digest_history.clear()

    atlas_int = get_atlas_integrator()
    atlas_int.vector_cache.clear()

    sig_int = get_sigmatics_integrator()
    sig_int.expression_cache.clear()

    logger.info("All UOR caches cleared")
