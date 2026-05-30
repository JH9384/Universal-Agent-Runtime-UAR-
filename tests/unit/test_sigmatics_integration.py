"""Tests for uar.core.sigmatics_integration — 100% coverage target."""

from unittest.mock import MagicMock, patch

from uar.core.sigmatics_integration import (
    Sigil,
    SigilExpression,
    SigmaticsIntegrator,
    create_sigil,
    create_sigil_expression,
    get_sigmatics_integrator,
    reset_sigmatics_integrator,
)


class TestSigil:
    def test_to_dict(self):
        s = Sigil(symbol="alpha", value=42, metadata={"x": 1})
        assert s.to_dict() == {
            "symbol": "alpha",
            "value": 42,
            "metadata": {"x": 1},
        }

    def test_post_init_none_metadata(self):
        s = Sigil(symbol="beta")
        assert s.metadata == {}


class TestSigilExpression:
    def test_evaluate_sum(self):
        sigils = [Sigil("a", 1), Sigil("b", 2), Sigil("c", "text")]
        expr = SigilExpression(sigils=sigils, operation="sum")
        assert expr.evaluate() == 3

    def test_evaluate_product(self):
        sigils = [Sigil("a", 2), Sigil("b", 3)]
        expr = SigilExpression(sigils=sigils, operation="product")
        assert expr.evaluate() == 6

    def test_evaluate_unknown(self):
        sigils = [Sigil("a", 1)]
        expr = SigilExpression(sigils=sigils, operation="unknown")
        assert expr.evaluate() is None

    def test_wrap_with_uor_none_result(self):
        sigils = [Sigil("a", 1)]
        expr = SigilExpression(sigils=sigils, operation="sum")
        uor = expr.wrap_with_uor()
        assert uor is not None
        assert expr.result == 1

    def test_wrap_with_uor_existing_result(self):
        sigils = [Sigil("a", 5)]
        expr = SigilExpression(sigils=sigils, operation="sum")
        expr.evaluate()
        uor = expr.wrap_with_uor(source="test")
        assert uor is not None


class TestSigmaticsIntegrator:
    def test_init_no_cli(self):
        integrator = SigmaticsIntegrator(use_cli=False)
        assert integrator.use_cli is False
        assert integrator.cli_available is False

    def test_init_cli_not_found(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = FileNotFoundError()
            integrator = SigmaticsIntegrator(use_cli=True)
        assert integrator.cli_available is False

    def test_init_cli_timeout(self):
        import subprocess
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)
            integrator = SigmaticsIntegrator(use_cli=True)
        assert integrator.cli_available is False

    def test_init_cli_available(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            integrator = SigmaticsIntegrator(use_cli=True)
        assert integrator.cli_available is True

    def test_create_sigil(self):
        integrator = SigmaticsIntegrator()
        sigil = integrator.create_sigil("x", 10, {"y": 2})
        assert sigil.symbol == "x"
        assert sigil.value == 10

    def test_create_expression(self):
        integrator = SigmaticsIntegrator()
        sigils = [Sigil("a", 1)]
        expr = integrator.create_expression(sigils, "sum")
        assert expr.operation == "sum"
        assert len(integrator.expression_cache) == 1

    def test_generate_expression_id(self):
        integrator = SigmaticsIntegrator()
        sigils = [Sigil("a"), Sigil("b")]
        expr = SigilExpression(sigils=sigils, operation="sum")
        eid = integrator._generate_expression_id(expr)
        assert eid == "sum:a-b"

    def test_evaluate_via_cli_not_available(self):
        integrator = SigmaticsIntegrator(use_cli=False)
        result = integrator.evaluate_via_cli({"op": "sum"})
        assert result is None

    def test_evaluate_via_cli_success(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"result": 42}'
            )
            integrator = SigmaticsIntegrator(use_cli=True)
            result = integrator.evaluate_via_cli({"op": "sum"})
        assert result == {"result": 42}

    def test_evaluate_via_cli_empty_stdout(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="   "
            )
            integrator = SigmaticsIntegrator(use_cli=True)
            result = integrator.evaluate_via_cli({"op": "sum"})
        assert result is None

    def test_evaluate_via_cli_non_json_stdout(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="not-json"
            )
            integrator = SigmaticsIntegrator(use_cli=True)
            result = integrator.evaluate_via_cli({"op": "sum"})
        assert result is None

    def test_evaluate_via_cli_error_returncode(self):
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="fail"
            )
            integrator = SigmaticsIntegrator(use_cli=True)
            result = integrator.evaluate_via_cli({"op": "sum"})
        assert result is None

    def test_evaluate_via_cli_timeout(self):
        import subprocess
        with patch(
            "uar.core.sigmatics_integration.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # _check_cli_availability
                subprocess.TimeoutExpired("cmd", 30),  # evaluate_via_cli
            ]
            integrator = SigmaticsIntegrator(use_cli=True)
            result = integrator.evaluate_via_cli({"op": "sum"})
        assert result is None

    def test_integrate_with_uor(self):
        integrator = SigmaticsIntegrator()
        sigils = [Sigil("a", 1)]
        expr = integrator.create_expression(sigils, "sum")
        uor = integrator.integrate_with_uor(expr, source="test")
        assert uor is not None

    def test_batch_process_sigils(self):
        integrator = SigmaticsIntegrator()
        sigils = [Sigil("a", 1), Sigil("b", 2)]
        results = integrator.batch_process_sigils(sigils, "sum")
        assert len(results) == 1


class TestGlobalFunctions:
    def test_get_sigmatics_integrator(self):
        reset_sigmatics_integrator()
        integrator = get_sigmatics_integrator()
        assert isinstance(integrator, SigmaticsIntegrator)
        # Second call returns cached instance
        integrator2 = get_sigmatics_integrator()
        assert integrator2 is integrator
        reset_sigmatics_integrator()

    def test_reset_sigmatics_integrator(self):
        reset_sigmatics_integrator()
        i1 = get_sigmatics_integrator()
        reset_sigmatics_integrator()
        i2 = get_sigmatics_integrator()
        assert i1 is not i2

    def test_create_sigil(self):
        reset_sigmatics_integrator()
        sigil = create_sigil("x", 10)
        assert sigil.symbol == "x"
        assert sigil.value == 10
        reset_sigmatics_integrator()

    def test_create_sigil_expression(self):
        reset_sigmatics_integrator()
        sigils = [Sigil("a", 1)]
        expr = create_sigil_expression(sigils, "sum")
        assert expr.operation == "sum"
        reset_sigmatics_integrator()
