"""Tests for UOR-ADDR-1 bounded JSON canonicalization.

Covers JsonValue, canonicalize_json, compute_uor_digest,
recursion limits, array/object bounds, case distinction, and
all supported hash algorithms.
"""

from unittest.mock import patch

import pytest

from uar.uor.bounded_json import (
    JsonCase,
    JsonValue,
    canonicalize_json,
    compute_uor_digest,
)


class TestJsonCase:
    def test_enum_values(self):
        assert JsonCase.NULL == 0
        assert JsonCase.FALSE == 1
        assert JsonCase.TRUE == 2
        assert JsonCase.NUMBER == 3
        assert JsonCase.STRING == 4
        assert JsonCase.ARRAY == 5
        assert JsonCase.OBJECT == 6


class TestJsonValueFromPython:
    def test_null(self):
        v = JsonValue.from_python(None)
        assert v.value is None
        assert v.case == JsonCase.NULL

    def test_false(self):
        v = JsonValue.from_python(False)
        assert v.value is False
        assert v.case == JsonCase.FALSE

    def test_true(self):
        v = JsonValue.from_python(True)
        assert v.value is True
        assert v.case == JsonCase.TRUE

    def test_int(self):
        v = JsonValue.from_python(42)
        assert v.value == 42
        assert v.case == JsonCase.NUMBER

    def test_float(self):
        v = JsonValue.from_python(3.14)
        assert v.value == 3.14
        assert v.case == JsonCase.NUMBER

    def test_string(self):
        v = JsonValue.from_python("hello")
        assert v.value == "hello"
        assert v.case == JsonCase.STRING

    def test_list(self):
        v = JsonValue.from_python([1, 2, 3])
        assert v.case == JsonCase.ARRAY
        assert len(v.value) == 3
        assert v.value[0].value == 1

    def test_dict_sorted_keys(self):
        v = JsonValue.from_python({"z": 1, "a": 2})
        assert v.case == JsonCase.OBJECT
        keys = list(v.value.keys())
        assert keys == ["a", "z"]

    def test_nested(self):
        v = JsonValue.from_python({"items": [1, {"key": "val"}]})
        assert v.case == JsonCase.OBJECT
        assert v.value["items"].case == JsonCase.ARRAY

    def test_unsupported_type(self):
        class Custom:
            pass

        with pytest.raises(TypeError, match="Unsupported type"):
            JsonValue.from_python(Custom())

    def test_recursion_limit(self):
        with patch("uar.uor.bounded_json.MAX_RECURSION_DEPTH", 5):
            nested = {}
            for _ in range(6):
                nested = {"inner": nested}
            with pytest.raises(RecursionError, match="exceeds"):
                JsonValue.from_python(nested)

    def test_array_length_limit(self):
        with patch("uar.uor.bounded_json.MAX_ARRAY_LENGTH", 3):
            with pytest.raises(ValueError, match="exceeds"):
                JsonValue.from_python([1, 2, 3, 4])

    def test_object_key_limit(self):
        with patch("uar.uor.bounded_json.MAX_OBJECT_KEYS", 2):
            with pytest.raises(ValueError, match="exceeds"):
                JsonValue.from_python({"a": 1, "b": 2, "c": 3})

    def test_recursion_limit_increases_sys_limit(self):
        import sys

        with patch.object(sys, "getrecursionlimit", return_value=100):
            with patch.object(sys, "setrecursionlimit") as mock_set:
                JsonValue.from_python({"a": 1})
                mock_set.assert_called_once()


class TestJsonValueToPython:
    def test_scalar_round_trip(self):
        for val in [None, False, True, 42, 3.14, "hello"]:
            v = JsonValue.from_python(val)
            assert v.to_python() == val

    def test_array_round_trip(self):
        v = JsonValue.from_python([1, "two", True])
        assert v.to_python() == [1, "two", True]

    def test_object_round_trip(self):
        v = JsonValue.from_python({"a": 1, "b": 2})
        assert v.to_python() == {"a": 1, "b": 2}

    def test_to_python_recursion_limit(self):
        with patch("uar.uor.bounded_json.MAX_RECURSION_DEPTH", 5):
            # 5 iterations -> max depth 5 == limit
            nested = {}
            for _ in range(5):
                nested = {"inner": nested}
            v = JsonValue.from_python(nested)
            v.to_python()
            # One more level pushes innermost past limit
            nested = {"inner": nested}
            with pytest.raises(RecursionError, match="exceeds"):
                JsonValue.from_python(nested)


class TestJsonValueToCanonicalBytes:
    def test_scalar_prefix(self):
        v = JsonValue.from_python(42)
        b = v.to_canonical_bytes()
        assert b[0] == JsonCase.NUMBER
        assert b[1:] == b"42"

    def test_string_prefix(self):
        v = JsonValue.from_python("hello")
        b = v.to_canonical_bytes()
        assert b[0] == JsonCase.STRING

    def test_case_distinction(self):
        """CT-T: 42 and \"42\" produce different canonical forms."""
        num = JsonValue.from_python(42)
        string = JsonValue.from_python("42")
        assert num.to_canonical_bytes() != string.to_canonical_bytes()

    def test_null_false_true_distinct(self):
        """CT-T: null, false, true are all distinct."""
        null = JsonValue.from_python(None)
        false = JsonValue.from_python(False)
        true = JsonValue.from_python(True)
        assert null.to_canonical_bytes() != false.to_canonical_bytes()
        assert false.to_canonical_bytes() != true.to_canonical_bytes()

    def test_array_prefix(self):
        v = JsonValue.from_python([1, 2])
        b = v.to_canonical_bytes()
        assert b[0] == JsonCase.ARRAY

    def test_object_prefix(self):
        v = JsonValue.from_python({"a": 1})
        b = v.to_canonical_bytes()
        assert b[0] == JsonCase.OBJECT

    def test_canonical_stability(self):
        """Same input always produces same canonical bytes."""
        a = JsonValue.from_python({"b": 2, "a": 1})
        b = JsonValue.from_python({"a": 1, "b": 2})
        assert a.to_canonical_bytes() == b.to_canonical_bytes()

    def test_nfc_normalization(self):
        """Unicode NFC is applied to strings."""
        # U+0041 U+0308 (A + combining diaeresis) should normalize to U+00C4
        v = JsonValue.from_python("A\u0308")
        b = v.to_canonical_bytes()
        # Should contain the precomposed form, not the decomposed
        assert "\u00c4".encode("utf-8") in b

    def test_to_canonical_bytes_recursion_limit(self):
        v = JsonValue.from_python({"a": 1})
        with patch("uar.uor.bounded_json.MAX_RECURSION_DEPTH", 0):
            with pytest.raises(RecursionError, match="exceeds"):
                v.to_canonical_bytes(depth=1)


class TestJsonValueComputeDigest:
    def test_sha256(self):
        v = JsonValue.from_python({"a": 1})
        d = v.compute_digest("sha256")
        assert d.startswith("sha256:")
        assert len(d.split(":")[1]) == 64

    def test_sha3_256(self):
        v = JsonValue.from_python({"a": 1})
        d = v.compute_digest("sha3_256")
        assert d.startswith("sha3_256:")
        assert len(d.split(":")[1]) == 64

    def test_blake3(self):
        import sys

        v = JsonValue.from_python({"a": 1})
        d = v.compute_digest("blake3")
        if sys.version_info >= (3, 14):
            # blake3 segfaults on Python 3.14+; expect fallback
            assert d.startswith("sha256:")
        elif "blake3" in d:
            assert len(d.split(":")[1]) == 64
        else:
            # fallback to sha256
            assert d.startswith("sha256:")

    def test_unsupported_algorithm(self):
        v = JsonValue.from_python({"a": 1})
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            v.compute_digest("md5")

    def test_digest_consistency(self):
        """Same input = same digest."""
        a = JsonValue.from_python({"b": 2, "a": 1})
        b = JsonValue.from_python({"a": 1, "b": 2})
        assert a.compute_digest("sha256") == b.compute_digest("sha256")

    def test_case_distinction_in_digest(self):
        """42 and \"42\" must have different digests."""
        num = JsonValue.from_python(42)
        string = JsonValue.from_python("42")
        assert num.compute_digest("sha256") != string.compute_digest("sha256")


class TestCanonicalizeJson:
    def test_basic_object(self):
        c = canonicalize_json({"b": 2, "a": 1})
        assert isinstance(c, str)
        # Should start with OBJECT case tag byte
        assert c[0] == chr(JsonCase.OBJECT)

    def test_array(self):
        c = canonicalize_json([1, 2, 3])
        assert c[0] == chr(JsonCase.ARRAY)

    def test_scalar(self):
        c = canonicalize_json("hello")
        assert c[0] == chr(JsonCase.STRING)

    def test_stability(self):
        c1 = canonicalize_json({"z": 1, "a": 2})
        c2 = canonicalize_json({"a": 2, "z": 1})
        assert c1 == c2

    def test_invalid_utf8_not_possible(self):
        """JCS produces ASCII-safe JSON, so decode always succeeds."""
        c = canonicalize_json({"emoji": "hello"})
        assert isinstance(c, str)


class TestComputeUorDigest:
    def test_sha256_default(self):
        d = compute_uor_digest({"a": 1})
        assert d.startswith("sha256:")

    def test_sha3_256(self):
        d = compute_uor_digest({"a": 1}, algorithm="sha3_256")
        assert d.startswith("sha3_256:")

    def test_stability(self):
        d1 = compute_uor_digest({"b": 2, "a": 1})
        d2 = compute_uor_digest({"a": 1, "b": 2})
        assert d1 == d2

    def test_case_distinction(self):
        """Different types with same JSON text must differ."""
        d1 = compute_uor_digest(42)
        d2 = compute_uor_digest("42")
        assert d1 != d2

    def test_unsupported_type_raises(self):
        class Custom:
            pass

        with pytest.raises(TypeError, match="Unsupported type"):
            compute_uor_digest(Custom())

    def test_recursion_error(self):
        with patch("uar.uor.bounded_json.MAX_RECURSION_DEPTH", 5):
            nested = {}
            for _ in range(6):
                nested = {"inner": nested}
            with pytest.raises(RecursionError):
                compute_uor_digest(nested)
