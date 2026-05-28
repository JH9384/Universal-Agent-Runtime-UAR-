"""Tests for JSON utilities.

Covers safe load, dump, parse, serialize, and validation.
"""

import json
import os
import tempfile
from pathlib import Path

from uar.core.json_utils import (
    fast_dumps,
    fast_dumps_bytes,
    json_load_safely,
    json_dump_safely,
    json_loads_safely,
    json_dumps_safely,
    validate_json_structure,
)


class TestFastDumps:
    """Fast serialization helpers."""

    def test_fast_dumps(self):
        result = fast_dumps({"a": 1})
        assert isinstance(result, str)
        assert "a" in result

    def test_fast_dumps_bytes(self):
        result = fast_dumps_bytes({"a": 1})
        assert isinstance(result, bytes)
        assert b"a" in result


class TestJsonLoadSafely:
    """Load JSON from file with fallback."""

    def test_load_valid(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"key": "value"}, f)
            path = f.name
        try:
            result = json_load_safely(Path(path))
            assert result == {"key": "value"}
        finally:
            os.unlink(path)

    def test_load_missing(self):
        result = json_load_safely(Path("/nonexistent/file.json"), default={})
        assert result == {}

    def test_load_invalid(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not json")
            path = f.name
        try:
            result = json_load_safely(Path(path), default=[])
            assert result == []
        finally:
            os.unlink(path)


class TestJsonDumpSafely:
    """Dump JSON to file with error handling."""

    def test_dump_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            ok = json_dump_safely({"a": 1}, path)
            assert ok is True
            assert path.exists()
            with open(path) as f:
                assert json.load(f) == {"a": 1}

    def test_dump_unserializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            ok = json_dump_safely({"a": {1, 2}}, path)
            assert ok is False

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "test.json"
            ok = json_dump_safely({"x": 2}, path)
            assert ok is True


class TestJsonLoadsSafely:
    """Parse JSON string with fallback."""

    def test_valid(self):
        result = json_loads_safely('{"a": 1}')
        assert result == {"a": 1}

    def test_invalid(self):
        result = json_loads_safely("not json", default=None)
        assert result is None

    def test_empty(self):
        result = json_loads_safely("")
        assert result is None


class TestJsonDumpsSafely:
    """Serialize to JSON string with fallback."""

    def test_valid(self):
        result = json_dumps_safely({"a": 1})
        assert result == '{"a": 1}'

    def test_sort_keys(self):
        result = json_dumps_safely({"z": 1, "a": 2}, sort_keys=True)
        assert result[2] == "a"  # 'a' comes first

    def test_indent(self):
        result = json_dumps_safely({"a": 1}, indent=2)
        assert "\n" in result

    def test_unserializable(self):
        result = json_dumps_safely({"a": object()})
        assert result is None


class TestValidateJsonStructure:
    """JSON structure validation."""

    def test_not_dict(self):
        assert validate_json_structure([]) is False

    def test_missing_required_key(self):
        assert validate_json_structure({}, required_keys=["a"]) is False

    def test_required_key_present(self):
        assert validate_json_structure({"a": 1}, required_keys=["a"]) is True

    def test_wrong_type(self):
        data = {"a": "str"}
        assert validate_json_structure(data, key_types={"a": int}) is False

    def test_correct_type(self):
        assert validate_json_structure({"a": 1}, key_types={"a": int}) is True

    def test_key_not_present_skips_type_check(self):
        assert validate_json_structure({}, key_types={"a": int}) is True
