"""Tests for uar.skills.physics_compute."""

from unittest.mock import MagicMock, patch

from uar.skills.physics_compute import (
    _convert_units,
    _calculate_distance,
    _transform_coordinate,
    _calculate_energy,
    _calculate_redshift,
    physics_compute,
    _execute_operation,
    _calculate_physics,
    _query_physics,
    _calculate_distance_from_value,
)


class TestConvertUnits:
    def test_success(self):
        mock_qty = MagicMock()
        mock_converted = MagicMock()
        mock_converted.value = 1000.0
        mock_u = MagicMock()
        mock_u.Quantity.return_value = mock_qty
        mock_qty.to.return_value = mock_converted
        mock_astropy = MagicMock()
        mock_astropy.units = mock_u
        with patch.dict("sys.modules", {
            "astropy": mock_astropy,
            "astropy.units": mock_u,
        }):
            result = _convert_units("1", "m", "km")
        assert result["success"] is True
        assert result["converted_value"] == "1000.0"


class TestCalculateDistance:
    def test_success(self):
        mock_sep = MagicMock()
        mock_sep.degree = 1.5
        mock_sep.arcsecond = 5400.0
        mock_c1 = MagicMock()
        mock_c1.separation.return_value = mock_sep
        mock_sky = MagicMock()
        mock_sky.return_value = mock_c1
        with patch.dict("sys.modules", {
            "astropy": MagicMock(),
            "astropy.coordinates": MagicMock(),
        }):
            import sys
            sys.modules["astropy.coordinates"].SkyCoord = mock_sky
            result = _calculate_distance("0", "0", "1", "1")
        assert result["success"] is True
        assert result["angular_distance_degrees"] == 1.5


class TestTransformCoordinate:
    def test_success(self):
        mock_transformed = MagicMock()
        mock_transformed.ra = "12h 30m"
        mock_transformed.dec = "+45d 00m"
        mock_c = MagicMock()
        mock_c.transform.return_value = mock_transformed
        mock_fk5 = MagicMock()
        mock_icrs = MagicMock()
        mock_gal = MagicMock()
        mock_sky = MagicMock()
        mock_sky.return_value = mock_c
        with patch.dict("sys.modules", {
            "astropy": MagicMock(),
            "astropy.coordinates": MagicMock(),
        }):
            import sys
            mod = sys.modules["astropy.coordinates"]
            mod.SkyCoord = mock_sky
            mod.FK5 = mock_fk5
            mod.ICRS = mock_icrs
            mod.Galactic = mock_gal
            result = _transform_coordinate("0", "0", "icrs", "fk5")
        assert result["success"] is True
        assert result["transformed_ra"] == "12h 30m"

    def test_unsupported_frame(self):
        mock_fk5 = MagicMock()
        mock_icrs = MagicMock()
        mock_gal = MagicMock()
        with patch.dict("sys.modules", {
            "astropy": MagicMock(),
            "astropy.coordinates": MagicMock(),
        }):
            import sys
            mod = sys.modules["astropy.coordinates"]
            mod.FK5 = mock_fk5
            mod.ICRS = mock_icrs
            mod.Galactic = mock_gal
            result = _transform_coordinate("0", "0", "bad", "icrs")
        assert result["success"] is False
        assert "Unsupported frame" in result["error"]


class TestCalculateEnergy:
    def test_success(self):
        mock_wave = MagicMock()
        mock_energy = MagicMock()
        mock_energy.value = 2.5
        mock_u = MagicMock()
        mock_u.Quantity.return_value = mock_wave
        mock_h = MagicMock()
        chain = mock_h.__mul__.return_value
        chain.__truediv__.return_value.to.return_value = mock_energy
        mock_astropy = MagicMock()
        mock_astropy.units = mock_u
        mock_astropy.constants = MagicMock()
        mock_astropy.constants.h = mock_h
        with patch.dict("sys.modules", {
            "astropy": mock_astropy,
            "astropy.units": mock_u,
            "astropy.constants": mock_astropy.constants,
        }):
            result = _calculate_energy("500 nm")
        assert result["success"] is True
        assert result["energy_eV"] == 2.5


class TestCalculateRedshift:
    def test_success(self):
        mock_dist = MagicMock()
        mock_dist.value = 100.0
        mock_cosmo = MagicMock()
        mock_cosmo.luminosity_distance.return_value = mock_dist
        mock_planck = MagicMock()
        mock_planck.return_value = mock_cosmo
        with patch.dict("sys.modules", {
            "astropy": MagicMock(),
            "astropy.cosmology": MagicMock(),
        }):
            import sys
            sys.modules["astropy.cosmology"].Planck18 = mock_cosmo
            result = _calculate_redshift("0.5")
        assert result["success"] is True
        assert result["luminosity_distance_Mpc"] == 100.0


class TestPhysicsCompute:
    def _make_ctx(self, metadata):
        ctx = MagicMock()
        ctx.goal.metadata = metadata
        return ctx

    def test_missing_astropy(self):
        with patch(
            "uar.skills.physics_compute.require_package"
        ) as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = physics_compute(self._make_ctx({}))
        assert result["status"] == "error"

    def test_missing_value(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            result = physics_compute(
                self._make_ctx({"physics_operation": "convert"})
            )
        assert result["status"] == "failed"
        assert "physics_value is required" in result["error"]

    def test_convert(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {
                "astropy": MagicMock(),
                "astropy.units": MagicMock(),
            }):
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "convert",
                        "physics_type": "unit",
                        "physics_value": "1",
                        "physics_from_unit": "m",
                        "physics_to_unit": "km",
                    })
                )
        assert result["status"] == "completed"

    def test_transform(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            mock_sky = MagicMock()
            mock_transformed = MagicMock()
            mock_transformed.ra = "10h"
            mock_transformed.dec = "+20d"
            mock_c = MagicMock()
            mock_c.transform.return_value = mock_transformed
            mock_sky.return_value = mock_c
            with patch.dict("sys.modules", {
                "astropy": MagicMock(),
                "astropy.coordinates": MagicMock(),
            }):
                import sys
                mod = sys.modules["astropy.coordinates"]
                mod.SkyCoord = mock_sky
                mod.FK5 = MagicMock()
                mod.ICRS = MagicMock()
                mod.Galactic = MagicMock()
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "transform",
                        "physics_type": "icrs",
                        "physics_value": "0",
                        "physics_from_unit": "0",
                        "physics_to_unit": "fk5",
                    })
                )
        assert result["status"] == "completed"

    def test_calculate_energy(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            mock_u = MagicMock()
            mock_wave = MagicMock()
            mock_energy = MagicMock()
            mock_energy.value = 2.0
            mock_u.Quantity.return_value = mock_wave
            with patch.dict("sys.modules", {
                "astropy": MagicMock(),
                "astropy.units": mock_u,
                "astropy.constants": MagicMock(),
            }):
                import sys
                sys.modules["astropy.constants"].h = MagicMock()
                sys.modules["astropy.constants"].c = MagicMock()
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "calculate",
                        "physics_type": "energy",
                        "physics_value": "500 nm",
                    })
                )
        assert result["status"] == "completed"

    def test_calculate_redshift(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            mock_dist = MagicMock()
            mock_dist.value = 100.0
            mock_cosmo = MagicMock()
            mock_cosmo.luminosity_distance.return_value = mock_dist
            with patch.dict("sys.modules", {
                "astropy": MagicMock(),
                "astropy.cosmology": MagicMock(),
            }):
                import sys
                sys.modules["astropy.cosmology"].Planck18 = mock_cosmo
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "calculate",
                        "physics_type": "redshift",
                        "physics_value": "0.5",
                    })
                )
        assert result["status"] == "completed"

    def test_calculate_distance(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            mock_sep = MagicMock()
            mock_sep.degree = 1.0
            mock_sep.arcsecond = 3600.0
            mock_c1 = MagicMock()
            mock_c1.separation.return_value = mock_sep
            mock_sky = MagicMock()
            mock_sky.return_value = mock_c1
            with patch.dict("sys.modules", {
                "astropy": MagicMock(),
                "astropy.coordinates": MagicMock(),
            }):
                import sys
                sys.modules["astropy.coordinates"].SkyCoord = mock_sky
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "calculate",
                        "physics_type": "distance",
                        "physics_value": "0,0,1,1",
                    })
                )
        assert result["status"] == "completed"

    def test_query(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            result = physics_compute(
                self._make_ctx({
                    "physics_operation": "query",
                    "physics_type": "info",
                    "physics_value": "test",
                })
            )
        assert result["status"] == "completed"
        assert result["message"] == "Query functionality - extend as needed"

    def test_unknown_operation(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            result = physics_compute(
                self._make_ctx({
                    "physics_operation": "bad_op",
                    "physics_type": "unit",
                    "physics_value": "1",
                })
            )
        assert result["status"] == "failed"
        assert "Unknown operation" in result["error"]

    def test_circuit_breaker_failure(self):
        with patch(
            "uar.skills.physics_compute.require_package", return_value=None
        ):
            with patch(
                "uar.skills.physics_compute._physics_cb.call"
            ) as mock_call:
                mock_call.side_effect = RuntimeError("boom")
                result = physics_compute(
                    self._make_ctx({
                        "physics_operation": "convert",
                        "physics_type": "unit",
                        "physics_value": "1",
                        "physics_from_unit": "m",
                        "physics_to_unit": "km",
                    })
                )
        assert result["status"] == "failed"


class TestExecuteOperation:
    def test_unknown_operation(self):
        result = _execute_operation("bad", "unit", "1", "m", "km")
        assert result["success"] is False
        assert "Unknown operation" in result["error"]


class TestCalculatePhysics:
    def test_unknown_type(self):
        result = _calculate_physics("bad", "1")
        assert result["success"] is False
        assert "Unknown calculation type" in result["error"]


class TestQueryPhysics:
    def test_success(self):
        result = _query_physics("info", "test")
        assert result["success"] is True
        assert result["query_type"] == "info"


class TestCalculateDistanceFromValue:
    def test_valid(self):
        mock_sep = MagicMock()
        mock_sep.degree = 2.0
        mock_sep.arcsecond = 7200.0
        mock_c1 = MagicMock()
        mock_c1.separation.return_value = mock_sep
        mock_sky = MagicMock()
        mock_sky.return_value = mock_c1
        with patch.dict("sys.modules", {
            "astropy": MagicMock(),
            "astropy.coordinates": MagicMock(),
        }):
            import sys
            sys.modules["astropy.coordinates"].SkyCoord = mock_sky
            result = _calculate_distance_from_value("0,0,1,1")
        assert result["success"] is True

    def test_invalid_format(self):
        result = _calculate_distance_from_value("0,0")
        assert result["success"] is False
        assert "Format should be" in result["error"]
