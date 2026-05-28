"""Tests for RDF format conversions.

Covers RDFConverter and OWLConverter.
"""

from unittest.mock import patch

from uar.uor.rdf_formats import (
    RDFLIB_AVAILABLE,
    RDFConversionResult,
    RDFConverter,
    OWLConverter,
)


class TestRDFConversionResult:
    """RDFConversionResult dataclass."""

    def test_to_dict(self):
        r = RDFConversionResult(
            success=True, data="test", format="turtle"
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["data"] == "test"
        assert d["format"] == "turtle"
        assert d["error"] is None

    def test_defaults(self):
        r = RDFConversionResult(success=False)
        assert r.data is None
        assert r.format is None
        assert r.error is None


class TestRDFConverterInit:
    """Converter initialization."""

    def test_init(self):
        c = RDFConverter()
        assert c.base_uri == "http://uor.foundation/"
        if RDFLIB_AVAILABLE:
            assert c.graph is not None
            assert c.uor_ns is not None


class TestRDFConverterJsonLD:
    """JSON-LD conversions."""

    def test_jsonld_to_rdf_dict(self):
        c = RDFConverter()
        jsonld = {
            "@context": {"name": "http://schema.org/name"},
            "name": "test",
        }
        result = c.jsonld_to_rdf(jsonld)
        assert result.success is True
        assert result.data is not None

    def test_jsonld_to_rdf_string(self):
        c = RDFConverter()
        ctx = {"@context": {"name": "http://schema.org/name"}, "name": "test"}
        jsonld = str(ctx).replace("'", '"')
        result = c.jsonld_to_rdf(jsonld)
        assert result.success is True

    def test_jsonld_to_rdf_bad_data(self):
        c = RDFConverter()
        result = c.jsonld_to_rdf("not valid json")
        assert result.success is False
        assert result.error is not None

    def test_rdf_to_jsonld(self):
        c = RDFConverter()
        # First create a graph
        from rdflib import Graph, URIRef, Literal, RDF

        g = Graph()
        s = URIRef("http://example.org/s")
        g.add((s, RDF.type, URIRef("http://example.org/Type")))
        g.add((s, URIRef("http://example.org/name"),
               Literal("test")))
        result = c.rdf_to_jsonld(g)
        assert result.success is True
        assert result.format == "json-ld"
        assert result.data is not None


class TestRDFConverterTurtle:
    """Turtle conversions."""

    def test_rdf_to_turtle(self):
        c = RDFConverter()
        from rdflib import Graph, URIRef, RDF

        g = Graph()
        s = URIRef("http://example.org/s")
        g.add((s, RDF.type, URIRef("http://example.org/Type")))
        result = c.rdf_to_turtle(g)
        assert result.success is True
        assert result.format == "turtle"
        assert "@prefix" in str(result.data) or "Type" in str(result.data)

    def test_turtle_to_rdf(self):
        c = RDFConverter()
        turtle = """
        @prefix ex: <http://example.org/> .
        ex:s a ex:Type .
        """
        result = c.turtle_to_rdf(turtle)
        assert result.success is True
        assert result.format == "rdf"

    def test_turtle_to_rdf_bad(self):
        c = RDFConverter()
        result = c.turtle_to_rdf("not valid turtle {{{")
        assert result.success is False


class TestRDFConverterEnvelope:
    """UOR envelope conversions."""

    def test_envelope_to_rdf(self):
        c = RDFConverter()
        envelope = {
            "digest": "sha256:abc123",
            "content": {"name": "test", "value": 42},
            "tags": ["a", "b"],
        }
        result = c.uor_envelope_to_rdf(envelope)
        assert result.success is True
        assert result.format == "rdf"

    def test_envelope_to_rdf_basic(self):
        c = RDFConverter()
        envelope = {
            "digest": "sha256:abc123",
            "content": {"name": "test"},
        }
        result = c.uor_envelope_to_rdf(envelope)
        assert result.success is True

    def test_envelope_roundtrip(self):
        c = RDFConverter()
        envelope = {
            "digest": "sha256:abc123",
            "content": {"name": "test"},
        }
        rdf_result = c.uor_envelope_to_rdf(envelope)
        assert rdf_result.success is True

        graph = rdf_result.data
        uri = "http://uor.foundation/envelope/sha256:abc123"
        back = c.rdf_to_uor_envelope(graph, uri)
        assert back.success is True
        assert "content" in back.data


class TestRDFConverterNotAvailable:
    """Graceful degradation when rdflib unavailable."""

    def test_jsonld_to_rdf_no_rdflib(self):
        with patch("uar.uor.rdf_formats.RDFLIB_AVAILABLE", False):
            c = RDFConverter()
            result = c.jsonld_to_rdf("{}")
            assert result.success is False
            assert "rdflib" in result.error.lower()

    def test_rdf_to_turtle_no_rdflib(self):
        with patch("uar.uor.rdf_formats.RDFLIB_AVAILABLE", False):
            c = RDFConverter()
            result = c.rdf_to_turtle(None)
            assert result.success is False
            assert "rdflib" in result.error.lower()


class TestOWLConverter:
    """OWL ontology conversion."""

    def test_schema_to_owl(self):
        c = OWLConverter()
        schema = {
            "title": "TestSchema",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "active": {"type": "boolean"},
                "score": {"type": "number"},
                "nested": {"type": "object"},
            },
        }
        result = c.schema_to_owl(schema)
        assert result.success is True
        assert result.format == "owl"

    def test_owl_to_turtle(self):
        c = OWLConverter()
        from rdflib import Graph, URIRef, RDF, OWL as OWL_NS

        g = Graph()
        g.add((URIRef("http://test/Ontology"), RDF.type, OWL_NS.Ontology))
        result = c.owl_to_turtle(g)
        assert result.success is True
        assert result.format == "turtle"

    def test_no_rdflib(self):
        with patch("uar.uor.rdf_formats.RDFLIB_AVAILABLE", False):
            c = OWLConverter()
            result = c.schema_to_owl({})
            assert result.success is False
            assert "rdflib" in result.error.lower()
