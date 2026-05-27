"""SHACL validation for UOR object constraints.

Provides SHACL (Shapes Constraint Language) validation for UOR objects,
enforcing advanced constraints beyond JSON Schema.

Heavy dependencies (``pyshacl``, ``rdflib``) are optional; when absent,
this module still imports cleanly and :data:`SHACL_AVAILABLE` is ``False``
so callers can degrade gracefully.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import pyshacl  # type: ignore[import-not-found]
    from rdflib import (  # type: ignore[import-not-found]
        Graph,
        Literal,
        Namespace,
        URIRef,
    )

    SHACL_AVAILABLE = True
except ImportError:
    SHACL_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "pyshacl not available. Install with: pip install pyshacl rdflib"
    )

    # Sentinels so module-level annotations referencing these names do
    # not raise NameError at class-definition time.
    pyshacl = None  # type: ignore[assignment]
    Graph = None  # type: ignore[assignment,misc]
    Literal = None  # type: ignore[assignment,misc]
    Namespace = None  # type: ignore[assignment,misc]
    URIRef = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


@dataclass
class ConstraintViolation:
    """Represents a SHACL constraint violation."""

    constraint: str
    path: str
    value: Any
    message: str
    severity: str = "violation"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "constraint": self.constraint,
            "path": self.path,
            "value": self.value,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class SHACLValidationResult:
    """Result of SHACL validation."""

    conforms: bool
    violations: List[ConstraintViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conforms": self.conforms,
            "violations": [v.to_dict() for v in self.violations],
            "violation_count": len(self.violations),
        }


class SHACLValidator:
    """SHACL validator for UOR objects."""

    def __init__(self):
        """Initialize SHACL validator."""
        self.shapes_graph: Optional[Graph] = None
        self.data_graph: Optional[Graph] = None
        self.namespace = Namespace("http://uor.foundation/schema#")

    def load_shacl_shapes(
        self, shapes_data: str, format: str = "turtle"
    ) -> bool:
        """Load SHACL shapes from data.

        Args:
            shapes_data: SHACL shapes data as string
            format: Format of the data (turtle, json-ld, xml, n3)

        Returns:
            True if loaded successfully, False otherwise
        """
        if not SHACL_AVAILABLE:
            logger.warning("SHACL validation not available")
            return False

        try:
            self.shapes_graph = Graph()
            self.shapes_graph.parse(data=shapes_data, format=format)
            logger.info(f"Loaded SHACL shapes from {format} format")
            return True
        except Exception as e:
            logger.error(f"Failed to load SHACL shapes: {e}")
            return False

    def load_shacl_from_file(self, file_path: str) -> bool:
        """Load SHACL shapes from file.

        Args:
            file_path: Path to SHACL shapes file

        Returns:
            True if loaded successfully, False otherwise
        """
        if not SHACL_AVAILABLE:
            logger.warning("SHACL validation not available")
            return False

        try:
            self.shapes_graph = Graph()
            self.shapes_graph.parse(file_path, format="turtle")
            logger.info(f"Loaded SHACL shapes from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load SHACL shapes from file: {e}")
            return False

    def create_simple_shape(
        self,
        shape_id: str,
        target_class: str,
        constraints: Dict[str, Any],
    ) -> str:
        """Create a simple SHACL shape programmatically.

        Args:
            shape_id: Identifier for the shape
            target_class: Target class for the shape
            constraints: Dictionary of property constraints

        Returns:
            Turtle representation of the shape
        """
        if not SHACL_AVAILABLE:
            return ""

        try:
            g = Graph()
            sh = Namespace("http://www.w3.org/ns/shacl#")
            ex = Namespace("http://example.org/")

            g.bind("sh", sh)
            g.bind("ex", ex)

            # Create shape
            shape = ex[shape_id]
            g.add((shape, sh.targetClass, URIRef(target_class)))
            g.add((shape, sh.NodeKind, sh.BlankNode))

            # Add constraints
            for prop_path, constraint in constraints.items():
                prop_shape = URIRef(f"{shape_id}/{prop_path}")
                g.add((shape, sh.property, prop_shape))
                g.add(
                    (
                        prop_shape,
                        sh.path,
                        URIRef(f"http://example.org/{prop_path}"),
                    )
                )

                # Add specific constraints
                if isinstance(constraint, dict):
                    if "minCount" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.minCount,
                                Literal(constraint["minCount"]),
                            )
                        )
                    if "maxCount" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.maxCount,
                                Literal(constraint["maxCount"]),
                            )
                        )
                    if "datatype" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.datatype,
                                URIRef(constraint["datatype"]),
                            )
                        )
                    if "minLength" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.minLength,
                                Literal(constraint["minLength"]),
                            )
                        )
                    if "maxLength" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.maxLength,
                                Literal(constraint["maxLength"]),
                            )
                        )
                    if "pattern" in constraint:
                        g.add(
                            (
                                prop_shape,
                                sh.pattern,
                                Literal(constraint["pattern"]),
                            )
                        )

            turtle_data = g.serialize(format="turtle")
            return turtle_data if isinstance(turtle_data, str) else turtle_data.decode("utf-8")  # type: ignore[union-attr]

        except Exception as e:
            logger.error(f"Failed to create SHACL shape: {e}")
            return ""

    def validate_object(
        self, object_data: Dict[str, Any], object_class: str
    ) -> SHACLValidationResult:
        """Validate UOR object against SHACL shapes.

        Args:
            object_data: Object data to validate
            object_class: Class of the object

        Returns:
            SHACLValidationResult with violations if any
        """
        if not SHACL_AVAILABLE:
            logger.warning("SHACL validation not available")
            return SHACLValidationResult(conforms=True)

        if not self.shapes_graph:
            logger.warning("No SHACL shapes loaded")
            return SHACLValidationResult(conforms=True)

        try:
            # Create data graph from object
            self.data_graph = Graph()
            ex = Namespace("http://example.org/")
            self.data_graph.bind("ex", ex)

            # Convert object to RDF
            obj_uri = ex[f"object_{hash(str(object_data))}"]
            self.data_graph.add(
                (
                    obj_uri,
                    URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                    URIRef(object_class),
                )
            )

            for key, value in object_data.items():
                prop_uri = ex[key]
                if isinstance(value, (str, int, float, bool)):
                    self.data_graph.add((obj_uri, prop_uri, Literal(value)))
                elif isinstance(value, list):
                    for item in value:
                        self.data_graph.add((obj_uri, prop_uri, Literal(item)))
                elif isinstance(value, dict):
                    # Handle nested objects
                    nested_uri = ex[f"{key}_{hash(str(value))}"]
                    self.data_graph.add((obj_uri, prop_uri, nested_uri))
                    for nested_key, nested_value in value.items():
                        nested_prop = ex[nested_key]
                        self.data_graph.add(
                            (nested_uri, nested_prop, Literal(nested_value))
                        )

            # Validate against SHACL shapes
            conforms, results_graph = pyshacl.validate(
                self.data_graph,
                shacl_graph=self.shapes_graph,
                ont_graph=None,
                inference="rdfs",
                abort_on_first=False,
                allow_info=True,
                meta_shacl=False,
                debug=False,
            )

            # Extract violations
            violations = []
            if not conforms:
                violations = self._extract_violations(results_graph)

            return SHACLValidationResult(
                conforms=conforms, violations=violations
            )

        except Exception as e:
            logger.error(f"SHACL validation failed: {e}")
            return SHACLValidationResult(
                conforms=False,
                violations=[
                    ConstraintViolation(
                        constraint="validation_error",
                        path="root",
                        value=object_data,
                        message=f"Validation error: {e}",
                        severity="error",
                    )
                ],
            )

    def _extract_violations(
        self, results_graph: Graph
    ) -> List[ConstraintViolation]:
        """Extract violations from SHACL validation results.

        Args:
            results_graph: RDF graph with validation results

        Returns:
            List of ConstraintViolation objects
        """
        violations = []
        sh = Namespace("http://www.w3.org/ns/shacl#")

        # Query for validation results
        for result in results_graph.subjects(
            predicate=URIRef(sh.resultSeverity)
        ):
            severity = str(
                results_graph.value(
                    subject=result, predicate=URIRef(sh.resultSeverity)
                )
            )
            if severity.endswith("Violation") or severity.endswith("Error"):
                # Extract violation details
                source = results_graph.value(
                    subject=result,
                    predicate=URIRef(sh.sourceConstraintComponent),
                )
                value = results_graph.value(
                    subject=result, predicate=URIRef(sh.value)
                )
                message = results_graph.value(
                    subject=result, predicate=URIRef(sh.resultMessage)
                )

                if source and value:
                    violations.append(
                        ConstraintViolation(
                            constraint=str(source),
                            path=str(value),
                            value=value,
                            message=str(message)
                            if message
                            else "Constraint violation",
                            severity=severity.split("/")[-1],
                        )
                    )

        return violations

    def validate_collection(
        self, objects: List[Dict[str, Any]], object_class: str
    ) -> Dict[str, SHACLValidationResult]:
        """Validate a collection of UOR objects.

        Args:
            objects: List of object data to validate
            object_class: Class of the objects

        Returns:
            Dictionary mapping object index to validation results
        """
        results = {}
        for i, obj in enumerate(objects):
            results[f"object_{i}"] = self.validate_object(obj, object_class)
        return results


class UORSHACLSchema:
    """Predefined SHACL schemas for UOR objects."""

    @staticmethod
    def get_object_envelope_schema() -> str:
        """Get SHACL schema for UOR object envelopes."""
        return """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix uor: <http://uor.foundation/schema#> .

uor:ObjectEnvelopeShape
    a sh:NodeShape ;
    sh:targetClass uor:ObjectEnvelope ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:digest ;
        sh:datatype xsd:string ;
        sh:pattern "^sha256:[a-f0-9]{64}$" ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:severity sh:Violation
    ] ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:mediaType ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:mode ;
        sh:datatype xsd:string ;
        sh:in ( "immutable_singular" "mutable_singular" "mutable_array" ) ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:schema ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .
"""

    @staticmethod
    def get_execution_record_schema() -> str:
        """Get SHACL schema for execution records."""
        return """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix uor: <http://uor.foundation/schema#> .

uor:ExecutionRecordShape
    a sh:NodeShape ;
    sh:targetClass uor:ExecutionRecord ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:execution_id ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:skill ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:PropertyShape ;
        sh:path uor:status ;
        sh:datatype xsd:string ;
        sh:in ( "success" "failure" "timeout" ) ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .
"""
