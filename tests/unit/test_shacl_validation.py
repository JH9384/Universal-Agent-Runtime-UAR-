"""Tests for uar.uor.shacl_validation."""

from unittest.mock import patch

from uar.uor.shacl_validation import (
    ConstraintViolation,
    SHACLValidationResult,
    SHACLValidator,
)


class TestConstraintViolation:
    def test_to_dict(self):
        v = ConstraintViolation("c1", "p", "v", "msg", "error")
        d = v.to_dict()
        assert d["constraint"] == "c1"
        assert d["severity"] == "error"


class TestSHACLValidationResult:
    def test_to_dict(self):
        v = ConstraintViolation("c", "p", "v", "m")
        r = SHACLValidationResult(conforms=False, violations=[v])
        d = r.to_dict()
        assert d["conforms"] is False
        assert d["violation_count"] == 1

    def test_to_dict_empty(self):
        r = SHACLValidationResult(conforms=True)
        d = r.to_dict()
        assert d["conforms"] is True
        assert d["violation_count"] == 0


class TestSHACLValidator:
    def test_init(self):
        v = SHACLValidator()
        assert v.shapes_graph is None

    def test_load_shacl_shapes_unavailable(self):
        v = SHACLValidator()
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            assert v.load_shacl_shapes("data") is False

    def test_load_shacl_from_file_unavailable(self):
        v = SHACLValidator()
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            assert v.load_shacl_from_file("/tmp/test.ttl") is False

    def test_create_simple_shape_unavailable(self):
        v = SHACLValidator()
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            assert v.create_simple_shape("id", "cls", {}) == ""

    def test_validate_object_unavailable(self):
        v = SHACLValidator()
        with patch("uar.uor.shacl_validation.SHACL_AVAILABLE", False):
            result = v.validate_object({"a": 1}, "http://example.org/cls")
            assert result.conforms is True

    def test_validate_object_no_shapes(self):
        v = SHACLValidator()
        result = v.validate_object({"a": 1}, "http://example.org/cls")
        assert result.conforms is True
