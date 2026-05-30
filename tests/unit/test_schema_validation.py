"""Tests for uar.uor.schema_validation."""

import json
from unittest.mock import patch, MagicMock

from uar.uor.schema_validation import UORSchemaValidator


class TestUORSchemaValidator:
    def test_init(self):
        v = UORSchemaValidator()
        assert "uor.schema.object.v1" in v.schemas

    def test_init_with_dir(self, tmp_path):
        schema = {"type": "object"}
        f = tmp_path / "test.json"
        f.write_text(json.dumps(schema))
        v = UORSchemaValidator(str(tmp_path))
        assert "test" in v.schemas

    def test_init_missing_dir(self):
        v = UORSchemaValidator("/nonexistent/dir/12345")
        assert len(v.schemas) == 2  # builtins only

    def test_load_schema(self):
        v = UORSchemaValidator()
        v.load_schema("custom", {"type": "string"})
        assert "custom" in v.schemas

    def test_validate_missing_schema(self):
        v = UORSchemaValidator()
        ok, errs = v.validate({}, "nope")
        assert ok is False
        assert errs == ["Schema not found"]

    def test_validate_valid(self):
        v = UORSchemaValidator()
        obj = {
            "digest": "sha256:" + "a" * 64,
            "mediaType": "text/plain",
            "mode": "immutable_singular",
            "schema": "test",
            "content": "hello",
        }
        ok, errs = v.validate(obj)
        assert ok is True
        assert errs == []

    def test_validate_missing_field(self):
        v = UORSchemaValidator()
        ok, errs = v.validate({}, "uor.schema.object.v1")
        assert ok is False
        assert any("Missing" in e for e in errs)

    def test_validate_wrong_type(self):
        v = UORSchemaValidator()
        obj = {
            "digest": 123,
            "mediaType": "text/plain",
            "mode": "immutable_singular",
            "schema": "test",
            "content": "hello",
        }
        ok, errs = v.validate(obj)
        assert ok is False
        assert any("type" in e for e in errs)

    def test_validate_pattern(self):
        v = UORSchemaValidator()
        obj = {
            "digest": "invalid",
            "mediaType": "text/plain",
            "mode": "immutable_singular",
            "schema": "test",
            "content": "hello",
        }
        ok, errs = v.validate(obj)
        assert ok is False
        assert any("pattern" in e for e in errs)

    def test_validate_enum(self):
        v = UORSchemaValidator()
        obj = {
            "digest": "sha256:" + "a" * 64,
            "mediaType": "text/plain",
            "mode": "invalid_mode",
            "schema": "test",
            "content": "hello",
        }
        ok, errs = v.validate(obj)
        assert ok is False
        assert any("invalid" in e.lower() for e in errs)

    def test_validate_envelope(self):
        v = UORSchemaValidator()
        ok, errs = v.validate_envelope({})
        assert ok is False

    def test_validate_execution_record(self):
        v = UORSchemaValidator()
        ok, errs = v.validate_execution_record({})
        assert ok is False

    def test_get_available_schemas(self):
        v = UORSchemaValidator()
        names = v.get_available_schemas()
        assert "uor.schema.object.v1" in names

    def test_load_uor_foundation_schema(self):
        v = UORSchemaValidator()
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"type": "object"}'
            mock_open.return_value.__enter__.return_value = mock_resp
            assert v.load_uor_foundation_schema() is True

    def test_load_uor_foundation_schema_bad_json(self):
        v = UORSchemaValidator()
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"not json"
            mock_open.return_value.__enter__.return_value = mock_resp
            assert v.load_uor_foundation_schema() is False

    def test_load_uor_foundation_schema_network_error(self):
        v = UORSchemaValidator()
        with patch("urllib.request.urlopen", side_effect=Exception("fail")):
            assert v.load_uor_foundation_schema() is False
