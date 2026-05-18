import pytest
from uar.uor import (
    JsonCase,
    JsonValue,
    canonicalize_json,
    compute_uor_digest,
    MAX_RECURSION_DEPTH,
    MAX_ARRAY_LENGTH,
    MAX_OBJECT_KEYS,
)


def test_uor_critical_identity_offline():
    # Based on UOR public identity: neg(bnot(x)) = succ(x) in R_8
    x = 42
    n = 8
    mod = 2 ** n

    bnot_x = x ^ (mod - 1)  # bitwise NOT in n-bit ring
    neg_bnot_x = (-bnot_x) % mod
    succ_x = (x + 1) % mod

    assert neg_bnot_x == succ_x


def test_uor_object_shape_alignment():
    # Minimal UOR-aligned envelope expectations
    obj = {
        "digest": "sha256:abc",
        "mediaType": "application/json",
        "attributes": {},
        "links": [],
        "content": {}
    }

    assert "digest" in obj
    assert "mediaType" in obj
    assert isinstance(obj["links"], list)
    assert isinstance(obj["attributes"], dict)


def test_typed_json_case_distinction_number_vs_string():
    """CT-T: Numbers and strings with same representation produce distinct digests."""
    num_obj = JsonValue.from_python(42)
    str_obj = JsonValue.from_python("42")

    assert num_obj.case == JsonCase.NUMBER
    assert str_obj.case == JsonCase.STRING

    num_digest = num_obj.compute_digest()
    str_digest = str_obj.compute_digest()

    assert num_digest != str_digest


def test_typed_json_case_distinction_boolean_values():
    """CT-T: null, false, and true are pairwise distinct."""
    null_obj = JsonValue.from_python(None)
    false_obj = JsonValue.from_python(False)
    true_obj = JsonValue.from_python(True)

    assert null_obj.case == JsonCase.NULL
    assert false_obj.case == JsonCase.FALSE
    assert true_obj.case == JsonCase.TRUE

    null_digest = null_obj.compute_digest()
    false_digest = false_obj.compute_digest()
    true_digest = true_obj.compute_digest()

    assert null_digest != false_digest
    assert null_digest != true_digest
    assert false_digest != true_digest


def test_typed_json_case_distinction_array_vs_object():
    """CT-T: Arrays and objects with same payload are distinguished by tag."""
    array_obj = JsonValue.from_python([1, 2, 3])
    object_obj = JsonValue.from_python({"0": 1, "1": 2, "2": 3})

    assert array_obj.case == JsonCase.ARRAY
    assert object_obj.case == JsonCase.OBJECT

    array_digest = array_obj.compute_digest()
    object_digest = object_obj.compute_digest()

    assert array_digest != object_digest


def test_bounded_recursion_depth_enforcement():
    """CT-B: Recursion depth is bounded to prevent stack overflow."""
    # Create a deeply nested structure
    deep_obj = []
    current = deep_obj
    for _ in range(MAX_RECURSION_DEPTH + 1):
        current.append([])
        current = current[-1]

    with pytest.raises(RecursionError):
        JsonValue.from_python(deep_obj)


def test_bounded_array_length_enforcement():
    """CT-B: Array length is bounded."""
    large_array = list(range(MAX_ARRAY_LENGTH + 1))

    with pytest.raises(ValueError):
        JsonValue.from_python(large_array)


def test_bounded_object_key_enforcement():
    """CT-B: Object key count is bounded."""
    large_obj = {str(i): i for i in range(MAX_OBJECT_KEYS + 1)}

    with pytest.raises(ValueError):
        JsonValue.from_python(large_obj)


def test_canonicalization_idempotence():
    """CP-K01: Canonicalization is idempotent - canonical input stays canonical."""
    obj = {"z": 3, "a": 1, "m": 2}
    json_value = JsonValue.from_python(obj)

    # Canonicalize once
    canonical1 = json_value.to_canonical_bytes()

    # Convert back to Python and canonicalize again
    python_obj = json_value.to_python()
    json_value2 = JsonValue.from_python(python_obj)
    canonical2 = json_value2.to_canonical_bytes()

    assert canonical1 == canonical2


def test_deep_key_permutation_invariance():
    """CP-K02: Key permutation invariance at any depth."""
    # JCS-RFC8785 sorts object keys but preserves array order
    obj1 = {"a": {"z": 1, "a": 2}, "b": {"y": 3, "x": 2}}
    obj2 = {"a": {"a": 2, "z": 1}, "b": {"x": 2, "y": 3}}

    digest1 = compute_uor_digest(obj1)
    digest2 = compute_uor_digest(obj2)

    # Objects should have sorted keys at any depth
    # These should produce the same digest after canonicalization
    assert digest1 == digest2


def test_canonicalize_json_function():
    """Test the public canonicalize_json function."""
    obj = {"b": 2, "a": 1}
    canonical = canonicalize_json(obj)

    # Should be a string
    assert isinstance(canonical, str)
    # Should contain sorted keys
    assert canonical.index('"a"') < canonical.index('"b"')


def test_compute_uor_digest_function():
    """Test the public compute_uor_digest function."""
    obj = {"key": "value"}
    digest = compute_uor_digest(obj)

    # Should start with sha256:
    assert digest.startswith("sha256:")
    # Should be a valid hex digest
    hex_part = digest.split(":")[1]
    assert len(hex_part) == 64
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_round_trip_conversion():
    """Test that Python -> JsonValue -> Python preserves structure."""
    original = {
        "null": None,
        "bool_true": True,
        "bool_false": False,
        "number": 42,
        "string": "hello",
        "array": [1, 2, 3],
        "object": {"nested": "value"}
    }

    json_value = JsonValue.from_python(original)
    recovered = json_value.to_python()

    assert recovered == original
