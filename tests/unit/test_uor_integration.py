"""Tests for uar.core.uor_integration."""

from uar.core.uor_integration import (
    UORObject,
    UORIntegrator,
    get_uor_integrator,
    reset_uor_integrator,
    wrap_input_data,
    wrap_output_data,
    verify_output_integrity,
)


class TestUORObject:
    def test_post_init(self):
        obj = UORObject(data={"key": "value"})
        assert obj.size is not None
        assert obj.media_type == "application/json"

    def test_post_init_str(self):
        obj = UORObject(data="hello")
        assert obj.media_type == "text/plain"

    def test_post_init_bytes(self):
        obj = UORObject(data=b"hello")
        assert obj.media_type == "application/octet-stream"

    def test_compute_digest(self):
        obj = UORObject(data={"key": "value"})
        digest = obj.compute_digest()
        assert digest.startswith("sha256:")
        assert obj.digest == digest

    def test_verify_integrity(self):
        obj = UORObject(data={"key": "value"})
        digest = obj.compute_digest()
        assert obj.verify_integrity(digest) is True
        assert obj.verify_integrity("wrong") is False

    def test_add_schema_extension(self):
        obj = UORObject(data={})
        obj.add_schema_extension("ext", "val")
        assert obj.schema_extensions["ext"] == "val"

    def test_get_base_attributes(self):
        obj = UORObject(data={"a": 1})
        obj.compute_digest()
        attrs = obj.get_base_attributes()
        assert "size" in attrs
        assert "mediaType" in attrs
        assert "digest" in attrs

    def test_add_provenance(self):
        obj = UORObject(data={})
        obj.add_provenance("test", "op")
        assert len(obj.provenance) == 1
        assert obj.provenance[0]["source"] == "test"

    def test_add_transformation(self):
        obj = UORObject(data={})
        obj.add_transformation("t", {"p": 1})
        assert len(obj.transformations) == 1


class TestUORIntegrator:
    def test_wrap_object(self):
        integrator = UORIntegrator()
        obj = integrator.wrap_object({"a": 1}, source="test")
        assert obj.digest is not None
        assert obj.digest in integrator.object_cache

    def test_unwrap_object(self):
        integrator = UORIntegrator()
        obj = integrator.wrap_object({"a": 1})
        assert integrator.unwrap_object(obj) == {"a": 1}

    def test_verify_object_chain(self):
        integrator = UORIntegrator()
        obj = integrator.wrap_object({"a": 1})
        assert integrator.verify_object_chain(obj, [obj.digest]) is True
        assert integrator.verify_object_chain(obj, ["wrong"]) is False

    def test_apply_transformation(self):
        integrator = UORIntegrator()
        obj = integrator.wrap_object({"a": 1})
        new_obj = integrator.apply_transformation(
            obj, "double", {}, lambda x: {k: v * 2 for k, v in x.items()}
        )
        assert new_obj.data == {"a": 2}
        assert len(new_obj.transformations) == 1

    def test_get_object_by_digest(self):
        integrator = UORIntegrator()
        obj = integrator.wrap_object({"a": 1})
        assert integrator.get_object_by_digest(obj.digest) is obj
        assert integrator.get_object_by_digest("nope") is None

    def test_get_digest_history(self):
        integrator = UORIntegrator()
        integrator.wrap_object({"a": 1}, source="src1")
        history = integrator.get_digest_history()
        assert len(history) == 1
        filtered = integrator.get_digest_history(source="src1")
        assert len(filtered) == 1
        filtered = integrator.get_digest_history(source="other")
        assert len(filtered) == 0


class TestGlobalFunctions:
    def test_get_and_reset(self):
        reset_uor_integrator()
        i1 = get_uor_integrator()
        i2 = get_uor_integrator()
        assert i1 is i2
        reset_uor_integrator()
        i3 = get_uor_integrator()
        assert i3 is not i1

    def test_wrap_input_data(self):
        reset_uor_integrator()
        obj = wrap_input_data({"test": 1})
        assert obj.digest is not None

    def test_wrap_output_data(self):
        reset_uor_integrator()
        obj = wrap_output_data({"result": 1})
        assert obj.digest is not None

    def test_verify_output_integrity(self):
        reset_uor_integrator()
        obj = wrap_output_data({"result": 1})
        assert verify_output_integrity(obj) is True
        assert verify_output_integrity(obj, obj.digest) is True
        assert verify_output_integrity(obj, "wrong") is False
