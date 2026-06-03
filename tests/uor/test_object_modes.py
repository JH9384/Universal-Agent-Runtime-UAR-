"""Tests for UOR object mode enforcement.

Covers ObjectMode, ObjectVersion, UORObject, ObjectModeEnforcer:
mode validation, mutation permissions, version history,
array element operations, and digest recomputation.
"""

import pytest

from uar.uor.object_modes import (
    ObjectMode,
    ObjectVersion,
    UORObject,
    ObjectModeEnforcer,
)


class TestObjectMode:
    def test_constants(self):
        assert ObjectMode.IMMUTABLE_SINGULAR == "immutable_singular"
        assert ObjectMode.MUTABLE_SINGULAR == "mutable_singular"
        assert ObjectMode.MUTABLE_ARRAY == "mutable_array"


class TestObjectVersion:
    def test_defaults(self):
        v = ObjectVersion(version=1, digest="sha256:abc", content="hello")
        assert v.version == 1
        assert v.digest == "sha256:abc"
        assert v.content == "hello"
        assert v.timestamp is not None
        assert v.metadata == {}


class TestUORObject:
    def test_defaults(self):
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"a": 1},
        )
        assert obj.version == 1
        assert obj.version_history == []
        assert obj.array_elements == []
        assert obj.schema == "uor.schema.object.v1"
        assert obj.mediaType == "application/json"
        assert obj.attributes == {}
        assert obj.links == []

    def test_with_optional_fields(self):
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
            attributes={"owner": "test"},
            links=[{"rel": "self", "href": "/abc"}],
        )
        assert obj.attributes["owner"] == "test"
        assert len(obj.links) == 1


class TestObjectModeEnforcerValidateMode:
    def test_valid_modes(self):
        enforcer = ObjectModeEnforcer()
        for mode in [
            ObjectMode.IMMUTABLE_SINGULAR,
            ObjectMode.MUTABLE_SINGULAR,
            ObjectMode.MUTABLE_ARRAY,
        ]:
            obj = UORObject(digest="sha256:abc", mode=mode, content="x")
            assert enforcer.validate_mode(obj) is True

    def test_invalid_mode(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(digest="sha256:abc", mode="unknown", content="x")
        assert enforcer.validate_mode(obj) is False


class TestObjectModeEnforcerCanModify:
    def test_immutable_not_modifiable(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content="x",
        )
        assert enforcer.can_modify(obj) is False

    def test_mutable_singular_modifiable(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content="x",
        )
        assert enforcer.can_modify(obj) is True

    def test_mutable_array_modifiable(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content="x",
        )
        assert enforcer.can_modify(obj) is True


class TestObjectModeEnforcerCanTransitionMode:
    def test_immutable_no_transitions(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content="x",
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_SINGULAR)
            is False
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_ARRAY)
            is False
        )

    def test_mutable_singular_self_transition(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content="x",
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_SINGULAR)
            is True
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_ARRAY)
            is False
        )

    def test_mutable_array_self_transition(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content="x",
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_ARRAY)
            is True
        )
        assert (
            enforcer.can_transition_mode(obj, ObjectMode.MUTABLE_SINGULAR)
            is False
        )


class TestObjectModeEnforcerUpdateContent:
    def test_mutable_singular_update(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        original_digest = obj.digest
        enforcer.update_content(obj, {"a": 2})
        assert obj.content == {"a": 2}
        assert obj.version == 2
        assert obj.digest != original_digest

    def test_mutable_array_update(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"a": 1},
        )
        enforcer.update_content(obj, {"a": 2})
        assert obj.content == {"a": 2}
        assert obj.version == 2

    def test_immutable_raises(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"a": 1},
        )
        with pytest.raises(ValueError, match="Cannot modify"):
            enforcer.update_content(obj, {"a": 2})

    def test_version_history_preserved(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        enforcer.update_content(obj, {"a": 2})
        assert len(obj.version_history) == 1
        assert obj.version_history[0].version == 1
        assert obj.version_history[0].content == {"a": 1}
        assert obj.version_history[0].digest == "sha256:abc"

    def test_version_history_skipped(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        enforcer.update_content(obj, {"a": 2}, preserve_history=False)
        assert len(obj.version_history) == 0

    def test_multiple_updates(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        enforcer.update_content(obj, {"a": 2})
        enforcer.update_content(obj, {"a": 3})
        assert obj.version == 3
        assert len(obj.version_history) == 2
        assert obj.version_history[0].version == 1
        assert obj.version_history[1].version == 2

    def test_timestamp_is_aware_utc(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        enforcer.update_content(obj, {"a": 2})
        ts = obj.version_history[0].timestamp
        assert ts.tzinfo is not None
        assert ts.utcoffset().total_seconds() == 0


class TestObjectModeEnforcerArrayOps:
    def test_add_element(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        original_digest = obj.digest
        enforcer.add_array_element(obj, {"item": 1})
        assert len(obj.array_elements) == 1
        assert obj.array_elements[0] == {"item": 1}
        assert obj.digest != original_digest

    def test_add_element_invalid_mode(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"base": True},
        )
        with pytest.raises(ValueError, match="Cannot add element"):
            enforcer.add_array_element(obj, {"item": 1})

    def test_remove_element(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        enforcer.add_array_element(obj, {"item": 1})
        enforcer.add_array_element(obj, {"item": 2})
        enforcer.remove_array_element(obj, 0)
        assert len(obj.array_elements) == 1
        assert obj.array_elements[0] == {"item": 2}

    def test_remove_element_invalid_index(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        enforcer.add_array_element(obj, {"item": 1})
        with pytest.raises(ValueError, match="Invalid index"):
            enforcer.remove_array_element(obj, 5)
        with pytest.raises(ValueError, match="Invalid index"):
            enforcer.remove_array_element(obj, -1)

    def test_remove_element_invalid_mode(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"base": True},
        )
        with pytest.raises(ValueError, match="Cannot remove element"):
            enforcer.remove_array_element(obj, 0)

    def test_get_array_elements(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        enforcer.add_array_element(obj, {"item": 1})
        assert enforcer.get_array_elements(obj) == [{"item": 1}]

    def test_get_array_elements_non_array_mode(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"base": True},
        )
        assert enforcer.get_array_elements(obj) == []


class TestObjectModeEnforcerComputeDigest:
    def test_mutable_singular_digest(self):
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"a": 1},
        )
        d = enforcer._compute_digest(obj)
        assert d.startswith("sha256:")

    def test_mutable_array_includes_elements(self):
        """Array digest must include both content and array_elements."""
        enforcer = ObjectModeEnforcer()
        obj1 = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        d1 = enforcer._compute_digest(obj1)

        obj2 = UORObject(
            digest="sha256:abc",
            mode=ObjectMode.MUTABLE_ARRAY,
            content={"base": True},
        )
        enforcer.add_array_element(obj2, {"item": 1})
        d2 = enforcer._compute_digest(obj2)

        assert d1 != d2
