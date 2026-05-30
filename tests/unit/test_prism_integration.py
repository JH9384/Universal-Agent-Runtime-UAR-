"""Tests for uar.core.prism_integration."""

from unittest.mock import patch

from uar.core.prism_integration import (
    PrismFacet,
    Prism,
    PrismIntegrator,
    create_prism,
    get_prism_integrator,
    reset_prism_integrator,
)


class TestPrismFacet:
    def test_default_metadata(self):
        f = PrismFacet("f1", "test", "hello")
        assert f.metadata == {}

    def test_provided_metadata(self):
        f = PrismFacet("f1", "test", "hello", metadata={"k": "v"})
        assert f.metadata == {"k": "v"}

    def test_transform_uppercase(self):
        f = PrismFacet("f1", "test", "hello")
        assert f.transform("uppercase") == "HELLO"

    def test_transform_lowercase(self):
        f = PrismFacet("f1", "test", "HELLO")
        assert f.transform("lowercase") == "hello"

    def test_transform_unknown(self):
        f = PrismFacet("f1", "test", "hello")
        assert f.transform("unknown") == "hello"

    def test_transform_non_string(self):
        f = PrismFacet("f1", "test", 42)
        assert f.transform("uppercase") == 42

    def test_wrap_with_uor(self):
        f = PrismFacet("f1", "test", "hello")
        with patch("uar.core.prism_integration.UORObject") as MockObj:
            mock = MockObj.return_value
            result = f.wrap_with_uor()
            assert result is mock
            mock.compute_digest.assert_called_once()


class TestPrism:
    def test_default_metadata(self):
        p = Prism("p1", [])
        assert p.metadata == {}

    def test_provided_metadata(self):
        p = Prism("p1", [], metadata={"k": "v"})
        assert p.metadata == {"k": "v"}

    def test_get_facet_found(self):
        f = PrismFacet("f1", "test", "hello")
        p = Prism("p1", [f])
        assert p.get_facet("f1") is f

    def test_get_facet_not_found(self):
        p = Prism("p1", [])
        assert p.get_facet("missing") is None

    def test_add_facet(self):
        p = Prism("p1", [])
        f = PrismFacet("f1", "test", "hello")
        p.add_facet(f)
        assert len(p.facets) == 1

    def test_refract(self):
        p = Prism("p1", [])
        f = PrismFacet("f1", "test", "hello")
        p.add_facet(f)
        with patch("uar.core.prism_integration.UORObject") as MockObj:
            mock = MockObj.return_value
            result = p.refract("data")
            assert result == [mock]


class TestPrismIntegrator:
    def test_create_prism(self):
        pi = PrismIntegrator()
        p = pi.create_prism("p1")
        assert p.prism_id == "p1"

    def test_integrate_with_uor(self):
        pi = PrismIntegrator()
        p = pi.create_prism("p1")
        with patch("uar.core.prism_integration.UORObject") as MockObj:
            mock = MockObj.return_value
            result = pi.integrate_with_uor(p)
            assert result is mock

    def test_refract_data(self):
        pi = PrismIntegrator()
        f = PrismFacet("f1", "test", "hello")
        pi.create_prism("p1", [f])
        with patch("uar.core.prism_integration.UORObject") as MockObj:
            mock = MockObj.return_value
            result = pi.refract_data("p1", "data")
            assert result == [mock]

    def test_refract_data_missing(self):
        pi = PrismIntegrator()
        result = pi.refract_data("unknown", "data")
        assert result == []


class TestGlobalFunctions:
    def test_get_prism_integrator_singleton(self):
        reset_prism_integrator()
        pi1 = get_prism_integrator()
        pi2 = get_prism_integrator()
        assert pi1 is pi2

    def test_create_prism_convenience(self):
        reset_prism_integrator()
        p = create_prism("cp1")
        assert p.prism_id == "cp1"
