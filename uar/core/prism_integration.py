"""Prism Integration Layer for UAR.

This module provides integration with the UOR Foundation's
prism component.

The prism component appears to be a core component of the
UOR Foundation ecosystem, likely providing:
- Data transformation and refraction capabilities
- Multi-faceted data representation
- Interface between different UOR components
- Data routing and distribution

This integration layer provides Python-native implementations
and bridges to the UOR prism framework.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .uor_integration import UORObject, ObjectMode

logger = logging.getLogger(__name__)


@dataclass
class PrismFacet:
    """Represents a facet in the prism component."""

    facet_id: str
    name: str
    data: Any
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def transform(self, transformation: str) -> Any:
        """Apply a transformation to the facet data."""
        # Placeholder for transformation logic
        if transformation == "uppercase" and isinstance(self.data, str):
            return self.data.upper()
        elif transformation == "lowercase" and isinstance(self.data, str):
            return self.data.lower()
        else:
            return self.data

    def wrap_with_uor(self, source: str = "prism") -> UORObject:
        """Wrap the facet in a UOR object."""
        uor_obj = UORObject(
            data={
                "facet_id": self.facet_id,
                "name": self.name,
                "data": self.data,
            },
            mode=ObjectMode.IMMUTABLE_SINGULAR
        )
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "prism_facet")
        uor_obj.add_schema_extension("prism_facet", True)

        return uor_obj


@dataclass
class Prism:
    """Represents a prism that can refract data into multiple facets."""

    prism_id: str
    facets: List[PrismFacet]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def add_facet(self, facet: PrismFacet) -> None:
        """Add a facet to the prism."""
        self.facets.append(facet)

    def get_facet(self, facet_id: str) -> Optional[PrismFacet]:
        """Get a facet by ID."""
        for facet in self.facets:
            if facet.facet_id == facet_id:
                return facet
        return None

    def refract(self, data: Any) -> List[UORObject]:
        """Refract data through all facets."""
        results = []

        for facet in self.facets:
            # Transform data through facet
            transformed = facet.transform("identity")
            facet.data = transformed

            # Wrap with UOR
            uor_obj = facet.wrap_with_uor()
            results.append(uor_obj)

        return results

    def wrap_with_uor(self, source: str = "prism") -> UORObject:
        """Wrap the prism in a UOR object."""
        uor_obj = UORObject(
            data={
                "prism_id": self.prism_id,
                "facet_count": len(self.facets),
                "facet_ids": [f.facet_id for f in self.facets],
            },
            mode=ObjectMode.MUTABLE_SINGULAR
        )
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "prism")
        uor_obj.add_schema_extension("prism", True)

        return uor_obj


class PrismIntegrator:
    """Main prism integration coordinator for UAR."""

    def __init__(self):
        self.enabled = True
        self.prisms: Dict[str, Prism] = {}

    def create_prism(
        self,
        prism_id: str,
        facets: Optional[List[PrismFacet]] = None
    ) -> Prism:
        """Create a prism."""
        prism = Prism(
            prism_id=prism_id,
            facets=facets or []
        )
        self.prisms[prism_id] = prism
        return prism

    def refract_data(
        self,
        prism_id: str,
        data: Any
    ) -> List[UORObject]:
        """Refract data through a prism."""
        if prism_id not in self.prisms:
            logger.warning(f"Prism {prism_id} not found")
            return []

        prism = self.prisms[prism_id]
        return prism.refract(data)

    def integrate_with_uor(
        self,
        prism: Prism,
        source: str = "prism"
    ) -> UORObject:
        """Integrate prism with UOR system."""
        uor_obj = prism.wrap_with_uor(source)

        # Add schema extensions for prism tracking
        uor_obj.add_schema_extension("prism_integration", True)
        uor_obj.add_schema_extension("prism_id", prism.prism_id)

        return uor_obj


# Global prism integrator instance
_prism_integrator: Optional[PrismIntegrator] = None


def get_prism_integrator() -> PrismIntegrator:
    """Get the global prism integrator instance."""
    global _prism_integrator
    if _prism_integrator is None:
        _prism_integrator = PrismIntegrator()
    return _prism_integrator


def reset_prism_integrator():
    """Reset the global prism integrator (useful for testing)."""
    global _prism_integrator
    _prism_integrator = None


def create_prism(
    prism_id: str,
    facets: Optional[List[PrismFacet]] = None
) -> Prism:
    """Convenience function to create a prism."""
    integrator = get_prism_integrator()
    return integrator.create_prism(prism_id, facets)
