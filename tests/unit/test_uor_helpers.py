"""Tests for uar.core.uor_helpers."""

from unittest.mock import MagicMock, patch

from uar.core.uor_helpers import (
    UORHelper,
    UORAssetHelper,
    UORMetricsHelper,
    UORValidationHelper,
    wrap_and_track,
    get_all_uor_digests,
    clear_uor_caches,
)


class TestUORHelper:
    def test_wrap_data(self):
        with patch("uar.core.uor_helpers.UORObject") as MockObj:
            mock = MagicMock()
            mock.digest = "d1"
            mock.size = 10
            mock.media_type = "text"
            mock.mode.value = "immutable"
            mock.provenance = []
            mock.transformations = []
            mock.schema_extensions = []
            MockObj.return_value = mock
            result = UORHelper.wrap_data_with_uor({"a": 1}, "test")
        assert result is mock
        mock.compute_digest.assert_called_once()
        mock.add_provenance.assert_called_once_with("test", "wrap")

    def test_verify_chain(self):
        obj = MagicMock()
        obj.provenance = [{"source": "s1"}]
        assert UORHelper.verify_uor_chain(obj, ["s1"]) is True
        assert UORHelper.verify_uor_chain(obj, ["s2"]) is False

    def test_get_summary(self):
        obj = MagicMock()
        obj.digest = "d1"
        obj.size = 10
        obj.media_type = "text"
        obj.mode.value = "immutable"
        obj.provenance = []
        obj.transformations = []
        obj.schema_extensions = []
        result = UORHelper.get_uor_summary(obj)
        assert result["digest"] == "d1"
        assert result["provenance_count"] == 0


class TestUORAssetHelper:
    def test_create_pipeline(self):
        with patch("uar.core.uor_helpers.wrap_input_data") as wrap:
            mock_uor = MagicMock()
            mock_uor.digest = "d1"
            wrap.return_value = mock_uor
            with patch("uar.core.uor_helpers.get_sigmatics_integrator") as gsi:
                sig_int = MagicMock()
                sig_uor = MagicMock()
                sig_uor.digest = "sd1"
                sig_int.integrate_with_uor.return_value = sig_uor
                gsi.return_value = sig_int
                with patch("uar.core.uor_helpers.get_atlas_integrator") as gai:
                    atlas_int = MagicMock()
                    atlas_uor = MagicMock()
                    atlas_uor.digest = "ad1"
                    atlas_int.integrate_with_uor.return_value = atlas_uor
                    gai.return_value = atlas_int
                    with patch(
                        "uar.core.uor_helpers.get_ego_guard_integrator"
                    ) as gegi:
                        eg_int = MagicMock()
                        eg_uor = MagicMock()
                        eg_uor.digest = "ed1"
                        eg_int.integrate_with_uor.return_value = eg_uor
                        gegi.return_value = eg_int
                        with patch(
                            "uar.core.uor_helpers.get_prism_integrator"
                        ) as gpi:
                            p_int = MagicMock()
                            p_uor = MagicMock()
                            p_uor.digest = "pd1"
                            p_int.integrate_with_uor.return_value = p_uor
                            gpi.return_value = p_int
                            with patch(
                                "uar.core.uor_helpers.get_uor_ecosystem"
                            ) as gue:
                                eco = MagicMock()
                                eco.status.return_value = {"ok": True}
                                gue.return_value = eco
                                result = (
                                    UORAssetHelper.create_computation_pipeline(
                                        {"x": 1},
                                        apply_sigil=True,
                                        apply_embedding=True,
                                        apply_security=True,
                                        apply_prism=True,
                                    )
                                )
        assert result["input_digest"] == "d1"
        assert result["sigil_digest"] == "sd1"
        assert result["embedding_digest"] == "ad1"
        assert result["policy_digest"] == "ed1"
        assert result["prism_digest"] == "pd1"

    def test_create_pipeline_defaults(self):
        with patch("uar.core.uor_helpers.wrap_input_data") as wrap:
            mock_uor = MagicMock()
            mock_uor.digest = "d1"
            wrap.return_value = mock_uor
            with patch("uar.core.uor_helpers.get_uor_ecosystem") as gue:
                eco = MagicMock()
                eco.status.return_value = {"ok": True}
                gue.return_value = eco
                result = UORAssetHelper.create_computation_pipeline(
                    {"x": 1}
                )
        assert result["input_digest"] == "d1"
        assert "sigil_digest" not in result
        assert "embedding_digest" not in result

    def test_get_ecosystem_status(self):
        with patch("uar.core.uor_helpers.get_uor_ecosystem") as gue:
            eco = MagicMock()
            eco.status.return_value = {"ok": True}
            gue.return_value = eco
            result = UORAssetHelper.get_ecosystem_status()
        assert result == {"ok": True}

    def test_reset_all(self):
        with patch("uar.core.uor_integration.reset_uor_integrator") as r1:
            with patch(
                "uar.core.sigmatics_integration.reset_sigmatics_integrator"
            ) as r2:
                with patch(
                    "uar.core.atlas_embeddings.reset_atlas_integrator"
                ) as r3:
                    with patch(
                        "uar.core.ego_guard_forge.reset_ego_guard_integrator"
                    ) as r4:
                        with patch(
                            "uar.core.prism_integration.reset_prism_integrator"
                        ) as r5:
                            with patch(
                                "uar.core.uor_ecosystem.reset_uor_ecosystem"
                            ) as r6:
                                UORAssetHelper.reset_all_integrators()
        r1.assert_called_once()
        r2.assert_called_once()
        r3.assert_called_once()
        r4.assert_called_once()
        r5.assert_called_once()
        r6.assert_called_once()


class TestUORMetricsHelper:
    def test_collect_metrics(self):
        with patch("uar.core.uor_helpers.get_uor_integrator") as g1:
            uor = MagicMock()
            uor.enabled = True
            uor.object_cache = {}
            uor.digest_history = {}
            g1.return_value = uor
            with patch("uar.core.uor_helpers.get_sigmatics_integrator") as g2:
                sig = MagicMock()
                sig.cli_available = True
                sig.expression_cache = {}
                g2.return_value = sig
                with patch(
                    "uar.core.uor_helpers.get_atlas_integrator"
                ) as g3:
                    atlas = MagicMock()
                    atlas.enabled = True
                    atlas.vector_cache = {}
                    g3.return_value = atlas
                    with patch(
                        "uar.core.uor_helpers.get_ego_guard_integrator"
                    ) as g4:
                        eg = MagicMock()
                        eg.enabled = True
                        eg.policies = {}
                        eg.audit_trail = []
                        g4.return_value = eg
                        with patch(
                            "uar.core.uor_helpers.get_prism_integrator"
                        ) as g5:
                            prism = MagicMock()
                            prism.enabled = True
                            prism.prisms = {}
                            g5.return_value = prism
                            result = UORMetricsHelper.collect_uor_metrics()
        assert "uor_integration" in result
        assert result["uor_integration"]["enabled"] is True

    def test_get_health_status(self):
        with patch.object(
            UORMetricsHelper, "collect_uor_metrics"
        ) as mock_collect:
            mock_collect.return_value = {
                "uor_integration": {"enabled": True},
                "atlas": {"enabled": False},
            }
            result = UORMetricsHelper.get_uor_health_status()
        assert result["uor_integration"] == "healthy"
        assert result["atlas"] == "disabled"


class TestUORValidationHelper:
    def test_valid_object(self):
        obj = MagicMock()
        obj.digest = "d1"
        obj.size = 10
        obj.media_type = "text"
        obj.provenance = [{"source": "s1"}]
        result = UORValidationHelper.validate_uor_object(obj)
        assert result["valid"] is True

    def test_invalid_object(self):
        obj = MagicMock()
        obj.digest = None
        obj.size = None
        obj.media_type = None
        obj.provenance = []
        result = UORValidationHelper.validate_uor_object(obj)
        assert result["valid"] is False
        assert len(result["warnings"]) == 3

    def test_validate_chain(self):
        obj1 = MagicMock()
        obj1.digest = "d1"
        obj1.size = 10
        obj1.media_type = "text"
        obj1.provenance = [{"source": "s1"}]
        obj2 = MagicMock()
        obj2.digest = "d2"
        obj2.size = 10
        obj2.media_type = "text"
        obj2.provenance = [{"digest": "d1"}]
        result = UORValidationHelper.validate_uor_chain([obj1, obj2])
        assert result["valid"] is True
        assert result["chain_breaks"] == []

    def test_chain_break(self):
        obj1 = MagicMock()
        obj1.digest = "d1"
        obj1.size = 10
        obj1.media_type = "text"
        obj1.provenance = [{"source": "s1"}]
        obj2 = MagicMock()
        obj2.digest = "d2"
        obj2.size = 10
        obj2.media_type = "text"
        obj2.provenance = [{"digest": "dx"}]
        result = UORValidationHelper.validate_uor_chain([obj1, obj2])
        assert "Break at index 1" in result["chain_breaks"]

    def test_invalid_object_in_chain(self):
        obj1 = MagicMock()
        obj1.digest = "d1"
        obj1.size = 10
        obj1.media_type = "text"
        obj1.provenance = [{"source": "s1"}]
        obj2 = MagicMock()
        obj2.digest = None
        obj2.size = None
        obj2.media_type = None
        obj2.provenance = []
        result = UORValidationHelper.validate_uor_chain([obj1, obj2])
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Object 1:" in e for e in result["errors"])


class TestConvenienceFunctions:
    def test_wrap_and_track(self):
        with patch("uar.core.uor_helpers.UORHelper.wrap_data_with_uor") as m:
            m.return_value = MagicMock()
            result = wrap_and_track({"a": 1}, "src")
            assert result is m.return_value
            m.assert_called_once_with({"a": 1}, "src")

    def test_get_all_digests(self):
        with patch("uar.core.uor_helpers.get_uor_integrator") as g1:
            uor = MagicMock()
            uor.object_cache = {"k": "v"}
            g1.return_value = uor
            with patch("uar.core.uor_helpers.get_atlas_integrator") as g2:
                atlas = MagicMock()
                atlas.vector_cache = {"k2": "v2"}
                g2.return_value = atlas
                with patch(
                    "uar.core.uor_helpers.get_sigmatics_integrator"
                ) as g3:
                    sig = MagicMock()
                    sig.expression_cache = {"k3": "v3"}
                    g3.return_value = sig
                    result = get_all_uor_digests()
        assert "uor_integration" in result
        assert "atlas_embeddings" in result
        assert "sigmatics" in result

    def test_clear_uor_caches(self):
        with patch("uar.core.uor_helpers.get_uor_integrator") as g1:
            uor = MagicMock()
            uor.object_cache = MagicMock()
            uor.digest_history = MagicMock()
            g1.return_value = uor
            with patch("uar.core.uor_helpers.get_atlas_integrator") as g2:
                atlas = MagicMock()
                atlas.vector_cache = MagicMock()
                g2.return_value = atlas
                with patch(
                    "uar.core.uor_helpers.get_sigmatics_integrator"
                ) as g3:
                    sig = MagicMock()
                    sig.expression_cache = MagicMock()
                    g3.return_value = sig
                    clear_uor_caches()
        uor.object_cache.clear.assert_called_once()
        uor.digest_history.clear.assert_called_once()
        atlas.vector_cache.clear.assert_called_once()
        sig.expression_cache.clear.assert_called_once()
