"""Tests for uar.uor.shacl_validation remaining coverage gaps."""

from unittest.mock import MagicMock, patch

import pytest

from uar.uor.shacl_validation import (
    SHACL_AVAILABLE,
    SHACLValidationResult,
    SHACLValidator,
    UORSHACLSchema,
)


class TestLoadFromFile:
    def test_load_from_file_bad_data(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        result = v.load_shacl_from_file("/nonexistent/path.ttl")
        assert result is False

    def test_load_from_file_exception(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        v.shapes_graph = MagicMock()
        with patch.object(
            v.shapes_graph, "parse", side_effect=RuntimeError("boom")
        ):
            result = v.load_shacl_from_file("/fake/path.ttl")
        assert result is False


class TestCreateSimpleShape:
    def test_non_dict_constraint(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        shape = v.create_simple_shape(
            "TestShape",
            "http://example.org/Test",
            {"name": "not_a_dict"},
        )
        assert "TestShape" in shape

    def test_exception(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        with patch(
            "uar.uor.shacl_validation.Graph"
        ) as mock_graph:
            mock_graph.side_effect = RuntimeError("boom")
            result = v.create_simple_shape("s", "c", {})
        assert result == ""

    def test_serialize_bytes(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        with patch(
            "uar.uor.shacl_validation.Graph"
        ) as mock_graph_cls:
            mock_g = MagicMock()
            mock_g.serialize.return_value = b"turtle data"
            mock_graph_cls.return_value = mock_g
            result = v.create_simple_shape("s", "c", {})
        assert result == "turtle data"


class TestValidateObject:
    def test_dict_value(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        shapes = UORSHACLSchema.get_object_envelope_schema()
        v.load_shacl_shapes(shapes, format="turtle")
        result = v.validate_object(
            {"nested": {"key": "value"}},
            "http://uor.foundation/schema#ObjectEnvelope",
        )
        assert isinstance(result, SHACLValidationResult)

    def test_violations(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        # Shape requiring a name with minCount 1
        shapes = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .

ex:TestShape a sh:NodeShape ;
    sh:targetClass ex:Test ;
    sh:property [ sh:path ex:name ; sh:minCount 1 ] .
"""
        v.load_shacl_shapes(shapes, format="turtle")
        # Object missing the required 'name' property
        result = v.validate_object(
            {}, "http://example.org/Test"
        )
        assert result.conforms is False
        assert len(result.violations) > 0


class TestExtractViolations:
    def test_extract_with_data(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        from rdflib import Graph, Literal, Namespace, URIRef

        v = SHACLValidator()
        sh = Namespace("http://www.w3.org/ns/shacl#")
        results_graph = Graph()
        result_uri = URIRef("http://example.org/result1")
        results_graph.add((
            result_uri,
            URIRef(sh.resultSeverity),
            URIRef("http://www.w3.org/ns/shacl#Violation"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.sourceConstraintComponent),
            URIRef("http://www.w3.org/ns/shacl#MinCountConstraintComponent"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.value),
            Literal("test_value"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.resultMessage),
            Literal("Value is required"),
        ))

        violations = v._extract_violations(results_graph)
        assert len(violations) == 1
        assert violations[0].constraint == (
            "http://www.w3.org/ns/shacl#MinCountConstraintComponent"
        )
        assert violations[0].message == "Value is required"
        assert violations[0].severity == "shacl#Violation"

    def test_extract_no_message(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        from rdflib import Graph, Literal, Namespace, URIRef

        v = SHACLValidator()
        sh = Namespace("http://www.w3.org/ns/shacl#")
        results_graph = Graph()
        result_uri = URIRef("http://example.org/result1")
        results_graph.add((
            result_uri,
            URIRef(sh.resultSeverity),
            URIRef("http://www.w3.org/ns/shacl#Violation"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.sourceConstraintComponent),
            URIRef("http://www.w3.org/ns/shacl#MinCountConstraintComponent"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.value),
            Literal("test_value"),
        ))

        violations = v._extract_violations(results_graph)
        assert len(violations) == 1
        assert violations[0].message == "Constraint violation"

    def test_extract_info_severity(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        from rdflib import Graph, Namespace, URIRef

        v = SHACLValidator()
        sh = Namespace("http://www.w3.org/ns/shacl#")
        results_graph = Graph()
        result_uri = URIRef("http://example.org/result1")
        results_graph.add((
            result_uri,
            URIRef(sh.resultSeverity),
            URIRef("http://www.w3.org/ns/shacl#Info"),
        ))

        violations = v._extract_violations(results_graph)
        assert len(violations) == 0

    def test_extract_missing_source(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        from rdflib import Graph, Literal, Namespace, URIRef

        v = SHACLValidator()
        sh = Namespace("http://www.w3.org/ns/shacl#")
        results_graph = Graph()
        result_uri = URIRef("http://example.org/result1")
        results_graph.add((
            result_uri,
            URIRef(sh.resultSeverity),
            URIRef("http://www.w3.org/ns/shacl#Violation"),
        ))
        results_graph.add((
            result_uri,
            URIRef(sh.value),
            Literal("test_value"),
        ))

        violations = v._extract_violations(results_graph)
        assert len(violations) == 0
