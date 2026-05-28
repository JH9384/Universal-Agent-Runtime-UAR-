"""RDF and semantic web format support for UOR objects.

Provides support for JSON-LD, Turtle, OWL, and other RDF formats
for UOR objects, enabling semantic interoperability.

``rdflib`` is an optional dependency; when absent this module imports
cleanly and :data:`RDFLIB_AVAILABLE` is ``False`` so callers can
degrade gracefully.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

try:
    from rdflib import (  # type: ignore[import-not-found]
        BNode,
        Graph,
        Literal,
        Namespace,
        URIRef,
    )
    from rdflib.namespace import (  # type: ignore[import-not-found]
        OWL,
        RDF,
        RDFS,
        XSD,
    )

    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "rdflib not available. Install with: pip install rdflib"
    )

    # Sentinels for clean module-level annotations without rdflib.
    BNode = None  # type: ignore[assignment,misc]
    Graph = None  # type: ignore[assignment,misc]
    Literal = None  # type: ignore[assignment,misc]
    Namespace = None  # type: ignore[assignment,misc]
    URIRef = None  # type: ignore[assignment,misc]
    OWL = RDF = RDFS = XSD = None  # type: ignore[assignment,misc]

try:
    import json

    JSON_AVAILABLE = True
except ImportError:
    JSON_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RDFConversionResult:
    """Result of RDF format conversion."""

    success: bool
    data: Optional[Union[str, Graph, Dict[str, Any]]] = None
    format: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "format": self.format,
            "error": self.error,
        }


class RDFConverter:
    """Converts UOR objects to/from RDF formats."""

    def __init__(self, base_uri: str = "http://uor.foundation/"):
        """Initialize RDF converter.

        Args:
            base_uri: Base URI for UOR namespace
        """
        self.base_uri = base_uri

        if RDFLIB_AVAILABLE:
            self.uor_ns = Namespace(base_uri)
            self.graph = Graph()
            self.graph.bind("uor", self.uor_ns)
            self.graph.bind("rdf", RDF)
            self.graph.bind("rdfs", RDFS)
            self.graph.bind("owl", OWL)
            self.graph.bind("xsd", XSD)
        else:
            self.uor_ns = None  # type: ignore[assignment]
            self.graph = None  # type: ignore[assignment]

    def jsonld_to_rdf(
        self, jsonld_data: str, context: Optional[Dict[str, Any]] = None
    ) -> RDFConversionResult:
        """Convert JSON-LD to RDF graph.

        Args:
            jsonld_data: JSON-LD string or dict
            context: Optional JSON-LD context

        Returns:
            RDFConversionResult with RDF graph
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for JSON-LD conversion",
            )

        try:
            graph = Graph()

            if isinstance(jsonld_data, str):
                if JSON_AVAILABLE:
                    jsonld_data = json.loads(jsonld_data)
                else:
                    return RDFConversionResult(
                        success=False,
                        error="json module not available",
                    )

            # Parse JSON-LD
            graph.parse(data=json.dumps(jsonld_data), format="json-ld")

            return RDFConversionResult(success=True, data=graph, format="rdf")
        except Exception:
            logger.exception("JSON-LD to RDF conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def rdf_to_jsonld(
        self, graph: Graph, context: Optional[Dict[str, Any]] = None
    ) -> RDFConversionResult:
        """Convert RDF graph to JSON-LD.

        Args:
            graph: RDF graph
            context: Optional JSON-LD context

        Returns:
            RDFConversionResult with JSON-LD string
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for JSON-LD conversion",
            )

        try:
            jsonld_data = graph.serialize(format="json-ld", context=context)

            return RDFConversionResult(
                success=True, data=jsonld_data, format="json-ld"
            )
        except Exception:
            logger.exception("RDF to JSON-LD conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def rdf_to_turtle(self, graph: Graph) -> RDFConversionResult:
        """Convert RDF graph to Turtle format.

        Args:
            graph: RDF graph

        Returns:
            RDFConversionResult with Turtle string
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for Turtle conversion",
            )

        try:
            turtle_data = graph.serialize(format="turtle")

            return RDFConversionResult(
                success=True, data=turtle_data, format="turtle"
            )
        except Exception:
            logger.exception("RDF to Turtle conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def turtle_to_rdf(self, turtle_data: str) -> RDFConversionResult:
        """Convert Turtle format to RDF graph.

        Args:
            turtle_data: Turtle format string

        Returns:
            RDFConversionResult with RDF graph
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for Turtle conversion",
            )

        try:
            graph = Graph()
            graph.parse(data=turtle_data, format="turtle")

            return RDFConversionResult(success=True, data=graph, format="rdf")
        except Exception:
            logger.exception("Turtle to RDF conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def uor_envelope_to_rdf(
        self, envelope: Dict[str, Any], envelope_uri: Optional[str] = None
    ) -> RDFConversionResult:
        """Convert UOR object envelope to RDF.

        Args:
            envelope: UOR object envelope dictionary
            envelope_uri: Optional URI for the envelope

        Returns:
            RDFConversionResult with RDF graph
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for RDF conversion",
            )

        try:
            graph = Graph()
            graph.bind("uor", self.uor_ns)

            # Create envelope URI
            if envelope_uri:
                uri = URIRef(envelope_uri)
            else:
                digest = envelope.get("digest", "")
                uri = self.uor_ns[f"envelope/{digest}"]

            # Add type
            graph.add((uri, RDF.type, self.uor_ns.ObjectEnvelope))

            # Add properties
            for key, value in envelope.items():
                if key == "content":
                    # Handle content separately as nested structure
                    content_uri = self.uor_ns[f"content/{digest}"]
                    graph.add((uri, self.uor_ns.content, content_uri))
                    self._add_content_to_graph(graph, content_uri, value)
                elif isinstance(value, list):
                    for item in value:
                        self._add_property_to_graph(graph, uri, key, item)
                else:
                    self._add_property_to_graph(graph, uri, key, value)

            return RDFConversionResult(success=True, data=graph, format="rdf")
        except Exception:
            logger.exception("UOR envelope to RDF conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def _add_property_to_graph(
        self, graph: Graph, subject: Union[URIRef, BNode], key: str, value: Any
    ):
        """Add a property to the RDF graph.

        Args:
            graph: RDF graph
            subject: Subject URI
            key: Property key
            value: Property value
        """
        predicate = self.uor_ns[key]  # type: ignore[index]

        if isinstance(value, (str, int, float, bool)):
            obj = Literal(value)
            graph.add((subject, predicate, obj))
        elif isinstance(value, dict):
            # Handle nested object
            bnode_obj = BNode()
            graph.add((subject, predicate, bnode_obj))
            for nested_key, nested_value in value.items():
                self._add_property_to_graph(  # type: ignore[arg-type]
                    graph, bnode_obj, nested_key, nested_value
                )

    def _add_content_to_graph(
        self, graph: Graph, content_uri: URIRef, content: Any
    ):
        """Add content to the RDF graph.

        Args:
            graph: RDF graph
            content_uri: Content URI
            content: Content data
        """
        if isinstance(content, dict):
            graph.add((content_uri, RDF.type, self.uor_ns.Content))
            for key, value in content.items():
                self._add_property_to_graph(graph, content_uri, key, value)
        else:
            graph.add((content_uri, RDF.type, self.uor_ns.Content))
            graph.add((content_uri, self.uor_ns.value, Literal(content)))

    def rdf_to_uor_envelope(
        self, graph: Graph, envelope_uri: str
    ) -> RDFConversionResult:
        """Convert RDF graph to UOR object envelope.

        Args:
            graph: RDF graph
            envelope_uri: URI of the envelope

        Returns:
            RDFConversionResult with UOR envelope dict
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for RDF conversion",
            )

        try:
            uri = URIRef(envelope_uri)
            envelope = {}

            # Extract properties
            for predicate, obj in graph.predicate_objects(subject=uri):
                predicate_str = str(predicate)
                predicate_name = (
                    predicate_str.split("#")[-1]
                    if "#" in predicate_str
                    else predicate_str.split("/")[-1]
                )

                if predicate_name == "content":
                    # Extract content
                    envelope["content"] = self._extract_content_from_graph(
                        graph, obj
                    )
                else:
                    # Extract simple property
                    if isinstance(obj, Literal):
                        envelope[predicate_name] = str(obj)
                    elif isinstance(obj, URIRef):
                        envelope[predicate_name] = str(obj)

            return RDFConversionResult(  # type: ignore[arg-type]
                success=True, data=envelope, format="envelope"
            )
        except Exception:
            logger.exception("RDF to UOR envelope conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def _extract_content_from_graph(
        self, graph: Graph, content_uri: Any
    ) -> Any:
        """Extract content from RDF graph.

        Args:
            graph: RDF graph
            content_uri: Content URI or BNode

        Returns:
            Content data
        """
        content = {}
        for predicate, obj in graph.predicate_objects(subject=content_uri):
            pred_str = str(predicate)
            predicate_name = (
                pred_str.split("#")[-1]
                if "#" in pred_str
                else pred_str.split("/")[-1]
            )

            if isinstance(obj, Literal):
                content[predicate_name] = str(obj)
            elif isinstance(obj, (URIRef, BNode)):
                # Recursively extract nested content
                nested = self._extract_content_from_graph(graph, obj)
                content[predicate_name] = nested

        return content


class OWLConverter:
    """Converts UOR schemas to OWL ontologies."""

    def __init__(self, base_uri: str = "http://uor.foundation/ontology#"):
        """Initialize OWL converter.

        Args:
            base_uri: Base URI for UOR ontology
        """
        self.base_uri = base_uri

        if RDFLIB_AVAILABLE:
            self.uor_ns = Namespace(base_uri)
            self.graph = Graph()
            self.graph.bind("uor", self.uor_ns)
            self.graph.bind("owl", OWL)
            self.graph.bind("rdf", RDF)
            self.graph.bind("rdfs", RDFS)
        else:
            self.uor_ns = None  # type: ignore[assignment]
            self.graph = None  # type: ignore[assignment]

    def schema_to_owl(self, schema: Dict[str, Any]) -> RDFConversionResult:
        """Convert JSON Schema to OWL ontology.

        Args:
            schema: JSON Schema dictionary

        Returns:
            RDFConversionResult with OWL graph
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for OWL conversion",
            )

        try:
            graph = Graph()
            graph.bind("uor", self.uor_ns)
            graph.bind("owl", OWL)

            # Create ontology
            ontology = self.uor_ns.Ontology
            graph.add((ontology, RDF.type, OWL.Ontology))

            # Convert schema to OWL classes and properties
            self._convert_schema_to_owl(graph, schema, self.uor_ns)

            return RDFConversionResult(success=True, data=graph, format="owl")
        except Exception:
            logger.exception("Schema to OWL conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )

    def _convert_schema_to_owl(
        self, graph: Graph, schema: Dict[str, Any], namespace: Namespace
    ):
        """Convert JSON Schema to OWL classes and properties.

        Args:
            graph: RDF graph
            schema: JSON Schema dictionary
            namespace: Namespace for URIs
        """
        schema_name = schema.get("title", "Unnamed")
        class_uri = namespace[schema_name]

        # Create OWL class
        graph.add((class_uri, RDF.type, OWL.Class))

        # Add properties from schema
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            prop_uri = namespace[prop_name]

            # Create OWL property
            prop_type = prop_schema.get("type", "string")
            if prop_type in ["string", "number", "integer", "boolean"]:
                graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            else:
                graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

            # Add domain and range
            graph.add((prop_uri, RDFS.domain, class_uri))

            if prop_type == "string":
                graph.add((prop_uri, RDFS.range, XSD.string))
            elif prop_type == "number":
                graph.add((prop_uri, RDFS.range, XSD.decimal))
            elif prop_type == "integer":
                graph.add((prop_uri, RDFS.range, XSD.integer))
            elif prop_type == "boolean":
                graph.add((prop_uri, RDFS.range, XSD.boolean))

    def owl_to_turtle(self, graph: Graph) -> RDFConversionResult:
        """Convert OWL graph to Turtle format.

        Args:
            graph: OWL graph

        Returns:
            RDFConversionResult with Turtle string
        """
        if not RDFLIB_AVAILABLE:
            return RDFConversionResult(
                success=False,
                error="rdflib not available for Turtle conversion",
            )

        try:
            turtle_data = graph.serialize(format="turtle")

            return RDFConversionResult(
                success=True, data=turtle_data, format="turtle"
            )
        except Exception:
            logger.exception("OWL to Turtle conversion failed")
            return RDFConversionResult(
                success=False, error="Conversion failed"
            )
