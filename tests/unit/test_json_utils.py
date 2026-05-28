"""Tests for uar.core.json_utils.

Covers JSON serialization, safe file I/O, and structural validation.
"""

import json

from uar.core.json_utils import (
    fast_dumps,
    fast_dumps_bytes,
    json_dump_safely,
    json_dumps_safely,
    json_load_safely,
    json_loads_safely,
    validate_json_structure,
)


class TestFastDumps:
    """Tests for fast JSON serialization."""

    def test_fast_dumps_dict(self):
        result = fast_dumps({"a": 1})
        assert json.loads(result) == {"a": 1}

    def test_fast_dumps_list(self):
        result = fast_dumps([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_fast_dumps_bytes(self):
        result = fast_dumps_bytes({"a": 1})
        assert isinstance(result, bytes)
        assert json.loads(result) == {"a": 1}


class TestJsonLoadSafely:
    """Tests for json_load_safely file reader."""

    def test_load_valid_json(self, tmp_path):
        file = tmp_path / "data.json"
        file.write_text('{"key": "value"}')
        result = json_load_safely(file)
        assert result == {"key": "value"}

    def test_load_missing_file_returns_default(self, tmp_path):
        file = tmp_path / "missing.json"
        result = json_load_safely(file, default={})
        assert result == {}

    def test_load_invalid_json_returns_default(self, tmp_path):
        file = tmp_path / "bad.json"
        file.write_text("not json")
        result = json_load_safely(file, default=[])
        assert result == []

    def test_load_no_default_returns_none(self, tmp_path):
        file = tmp_path / "missing.json"
        result = json_load_safely(file)
        assert result is None


class TestJsonDumpSafely:
    """Tests for json_dump_safely file writer."""

    def test_dump_valid_data(self, tmp_path):
        file = tmp_path / "out.json"
        success = json_dump_safely({"a": 1}, file)
        assert success is True
        assert json.loads(file.read_text()) == {"a": 1}

    def test_dump_creates_parent_dirs(self, tmp_path):
        file = tmp_path / "deep" / "nested" / "out.json"
        success = json_dump_safely({"a": 1}, file)
        assert success is True
        assert file.exists()

    def test_dump_sort_keys(self, tmp_path):
        file = tmp_path / "sorted.json"
        json_dump_safely({"z": 1, "a": 2}, file, sort_keys=True)
        content = file.read_text()
        assert content.index("a") < content.index("z")

    def test_dump_indent(self, tmp_path):
        file = tmp_path / "pretty.json"
        json_dump_safely({"a": 1}, file, indent=2)
        content = file.read_text()
        assert "\n" in content
        assert "  " in content

    def test_dump_unserializable_returns_false(self, tmp_path):
        file = tmp_path / "fail.json"
        success = json_dump_safely({"func": lambda: None}, file)
        assert success is False


class TestJsonLoadsSafely:
    """Tests for json_loads_safely string parser."""

    def test_parse_valid_string(self):
        result = json_loads_safely('{"a": 1}')
        assert result == {"a": 1}

    def test_parse_invalid_string_returns_default(self):
        result = json_loads_safely("not json", default={})
        assert result == {}

    def test_parse_none_string_returns_default(self):
        result = json_loads_safely("", default=[])
        assert result == []


class TestJsonDumpsSafely:
    """Tests for json_dumps_safely string serializer."""

    def test_serialize_valid(self):
        result = json_dumps_safely({"a": 1})
        assert json.loads(result) == {"a": 1}

    def test_serialize_sort_keys(self):
        result = json_dumps_safely({"z": 1, "a": 2}, sort_keys=True)
        assert result.index("a") < result.index("z")

    def test_serialize_indent(self):
        result = json_dumps_safely({"a": 1}, indent=2)
        assert "\n" in result

    def test_serialize_unserializable_returns_none(self):
        result = json_dumps_safely({"func": lambda: None})
        assert result is None


class TestValidateJsonStructure:
    """Tests for validate_json_structure."""

    def test_valid_dict_no_requirements(self):
        assert validate_json_structure({"a": 1}) is True

    def test_non_dict_returns_false(self):
        assert validate_json_structure("not a dict") is False

    def test_missing_required_key(self):
        assert validate_json_structure({}, required_keys=["id"]) is False

    def test_present_required_key(self):
        assert (
            validate_json_structure(
                {"id": "1"}, required_keys=["id"]
            )
            is True
        )

    def test_wrong_type(self):
        assert (
            validate_json_structure(
                {"count": "one"},
                key_types={"count": int},
            )
            is False
        )

    def test_correct_type(self):
        assert (
            validate_json_structure(
                {"count": 1},
                key_types={"count": int},
            )
            is True
        )

    def test_key_type_missing_key_ignored(self):
        """If key is absent, type check is skipped."""
        assert (
            validate_json_structure(
                {},
                key_types={"count": int},
            )
            is True
        )

    def test_combined_requirements_and_types(self):
        assert (
            validate_json_structure(
                {"id": "1", "count": 5},
                required_keys=["id"],
                key_types={"count": int},
            )
            is True
        )
