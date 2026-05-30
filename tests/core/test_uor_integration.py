"""Tests for uar.core.uor_integration missed branches."""

from unittest.mock import patch

from uar.core.uor_integration import (
    UORObject,
    UORIntegrator,
    get_uor_integrator,
    reset_uor_integrator,
    wrap_input_data,
    wrap_output_data,
    verify_output_integrity,
)


class TestUORObjectBranches:
    def test_compute_size_exception(self):
        with patch(
            "uar.core.uor_integration.json.dumps", side_effect=TypeError("bad")
        ):
            obj = UORObject(data="test")
        assert obj.size > 0

    def test_infer_media_type_else(self):
        class CustomObj:
            pass

        obj = UORObject(data=CustomObj())
        assert obj.media_type == "application/json"

    def test_compute_digest_exception(self):
        obj = UORObject(data="test")
        with patch(
            "uar.core.uor_integration.json.dumps", side_effect=TypeError("bad")
        ):
            digest = obj.compute_digest()
        assert digest is not None
        assert digest.startswith("sha256:")

    def test_size_and_media_type_provided(self):
        obj = UORObject(data="test", size=100, media_type="text/html")
        assert obj.size == 100
        assert obj.media_type == "text/html"

    def test_add_provenance_timestamp(self):
        from datetime import datetime, timezone

        obj = UORObject(data="test")
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        obj.add_provenance("src", "op", ts)
        assert len(obj.provenance) == 1
        assert obj.provenance[0]["timestamp"] == "2024-01-01T00:00:00+00:00"


class TestUORIntegratorBranches:
    def setup_method(self):
        reset_uor_integrator()

    def test_wrap_object_no_digest(self):
        integrator = UORIntegrator()
        with patch.object(
            UORObject, "compute_digest", return_value=None
        ):
            obj = integrator.wrap_object("data")
            assert obj.digest is None
        assert len(integrator.digest_history) == 1

    def test_apply_transformation_no_digest(self):
        integrator = UORIntegrator()
        obj = UORObject(data="original")
        obj.compute_digest()
        with patch.object(
            UORObject, "compute_digest", return_value=None
        ):
            new_obj = integrator.apply_transformation(
                obj, "double", {}, lambda x, **kw: x * 2
            )
            assert new_obj.digest is None

    def test_get_digest_history_filter(self):
        integrator = UORIntegrator()
        integrator.wrap_object("a", source="src1")
        integrator.wrap_object("b", source="src2")
        history = integrator.get_digest_history(source="src1")
        assert len(history) == 1
        assert history[0]["source"] == "src1"


class TestGlobalFunctions:
    def setup_method(self):
        reset_uor_integrator()

    def test_get_uor_integrator_singleton(self):
        i1 = get_uor_integrator()
        i2 = get_uor_integrator()
        assert i1 is i2

    def test_wrap_input_output(self):
        obj = wrap_input_data("hello")
        assert obj.data == "hello"
        obj2 = wrap_output_data("world")
        assert obj2.data == "world"

    def test_verify_output_integrity_no_expected(self):
        obj = UORObject(data="test")
        obj.compute_digest()
        assert verify_output_integrity(obj) is True

    def test_verify_output_integrity_with_expected(self):
        obj = UORObject(data="test")
        expected = obj.compute_digest()
        assert verify_output_integrity(obj, expected) is True
