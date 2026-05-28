"""Tests for SHACL validation.

Covers SHACLValidator, ConstraintViolation, SHACLValidationResult,
and UORSHACLSchema.
"""

from unittest.mock import patch

import pytest

from uar.uor.shacl_validation import (
    SHACL_AVAILABLE,
    ConstraintViolation,
    SHACLValidationResult,
    SHACLValidator,
    UORSHACLSchema,
)


class TestConstraintViolation:
    """ConstraintViolation dataclass."""

    def test_to_dict(self):
        v = ConstraintViolation(
            constraint="minCount",
            path="name",
            value="",
            message="Required",
            severity="violation",
        )
        d = v.to_dict()
        assert d["constraint"] == "minCount"
        assert d["path"] == "name"
        assert d["severity"] == "violation"

    def test_defaults(self):
        v = ConstraintViolation(
            constraint="test", path="p", value=1, message="m"
        )
        assert v.severity == "violation"


class TestSHACLValidationResult:
    """SHACLValidationResult dataclass."""

    def test_to_dict(self):
        r = SHACLValidationResult(
            conforms=False,
            violations=[
                ConstraintViolation(
                    constraint="c", path="p", value=1, message="m"
                )
            ],
        )
        d = r.to_dict()
        assert d["conforms"] is False
        assert d["violation_count"] == 1
        assert len(d["violations"]) == 1

    def test_conforms_no_violations(self):
        r = SHACLValidationResult(conforms=True)
        d = r.to_dict()
        assert d["conforms"] is True
        assert d["violation_count"] == 0


class TestSHACLValidatorInit:
    """Validator initialization."""

    def test_init(self):
        v = SHACLValidator()
        assert v.shapes_graph is None
        assert v.data_graph is None


class TestSHACLValidatorLoadShapes:
    """Loading SHACL shapes."""

    def test_load_shapes_turtle(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        shapes = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .

ex:TestShape a sh:NodeShape ;
    sh:targetClass ex:Test ;
    sh:property [ sh:path ex:name ; sh:minCount 1 ] .
"""
        result = v.load_shacl_shapes(shapes, format="turtle")
        assert result is True
        assert v.shapes_graph is not None

    def test_load_shapes_bad_format(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        result = v.load_shacl_shapes("not valid turtle", format="turtle")
        assert result is False

    def test_load_shapes_not_available(self):
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            v = SHACLValidator()
            result = v.load_shacl_shapes("", format="turtle")
            assert result is False

    def test_load_from_file_not_available(self):
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            v = SHACLValidator()
            result = v.load_shacl_from_file("/fake/path")
            assert result is False


class TestSHACLValidatorCreateShape:
    """Programmatic shape creation."""

    def test_create_simple_shape(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        constraints = {
            "name": {"minCount": 1, "maxCount": 1, "datatype": "string"},
            "email": {"minLength": 5, "pattern": "@"},
        }
        shape = v.create_simple_shape(
            "PersonShape", "http://example.org/Person", constraints
        )
        assert "PersonShape" in shape
        assert "sh:targetClass" in shape
        assert "sh:minCount" in shape

    def test_create_shape_not_available(self):
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            v = SHACLValidator()
            result = v.create_simple_shape("s", "c", {})
            assert result == ""


class TestSHACLValidatorValidate:
    """Object validation against shapes."""

    def test_validate_no_shapes(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        result = v.validate_object({"name": "test"}, "http://example.org/Test")
        assert result.conforms is True

    def test_validate_with_shapes(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        shapes = UORSHACLSchema.get_object_envelope_schema()
        v.load_shacl_shapes(shapes, format="turtle")
        result = v.validate_object(
            {"digest": "sha256:a" * 32, "mediaType": "text/plain"},
            "http://uor.foundation/schema#ObjectEnvelope",
        )
        # Object doesn't fully conform but validation runs
        assert isinstance(result.conforms, bool)

    def test_validate_nested_object(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        result = v.validate_object(
            {"name": "test", "nested": {"key": "value"}},
            "http://example.org/Test",
        )
        assert result.conforms is True

    def test_validate_not_available(self):
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            v = SHACLValidator()
            result = v.validate_object({}, "c")
            assert result.conforms is True

    def test_validate_exception(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        shapes = UORSHACLSchema.get_object_envelope_schema()
        v.load_shacl_shapes(shapes, format="turtle")
        with patch("pyshacl.validate", side_effect=ValueError("boom")):
            result = v.validate_object({"a": 1}, "c")
        assert result.conforms is False
        assert len(result.violations) == 1
        assert result.violations[0].severity == "error"


class TestValidateCollection:
    """Batch validation."""

    def test_validate_collection(self):
        if not SHACL_AVAILABLE:
            pytest.skip("pyshacl not available")
        v = SHACLValidator()
        objects = [{"name": "a"}, {"name": "b"}]
        results = v.validate_collection(objects, "http://example.org/Test")
        assert len(results) == 2
        assert "object_0" in results
        assert "object_1" in results


class TestUORSHACLSchema:
    """Predefined schemas."""

    def test_object_envelope_schema(self):
        s = UORSHACLSchema.get_object_envelope_schema()
        assert "ObjectEnvelopeShape" in s
        assert "sh:targetClass" in s
        assert "sh:minCount" in s

    def test_execution_record_schema(self):
        s = UORSHACLSchema.get_execution_record_schema()
        assert "ExecutionRecordShape" in s
        assert "execution_id" in s
        assert "sh:in" in s
