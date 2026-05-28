"""Tests for uar.core.sandbox."""

import pytest

from uar.core.sandbox import (
    WASMSandbox,
    _validate_expression,
    _restricted_eval_in_subprocess,
    sandbox_eval,
)


class TestValidateExpression:
    def test_safe_expression_passes(self):
        _validate_expression("2 + 3 * 4")
        _validate_expression("(10 - 5) / 2.5")
        _validate_expression("2^3 + 1")

    @pytest.mark.parametrize(
        "bad",
        [
            "__import__('os')",
            "eval('1')",
            "import os",
            "os.system('ls')",
            "getattr(__builtins__, 'open')",
        ],
    )
    def test_unsafe_tokens_rejected(self, bad):
        with pytest.raises(ValueError, match="unsafe"):
            _validate_expression(bad)

    def test_unsafe_char_rejected(self):
        with pytest.raises(ValueError, match="unsafe character"):
            _validate_expression("2; 3")

    def test_empty_expression_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            _validate_expression("  ")


class TestRestrictedEvalInSubprocess:
    def test_simple_addition(self):
        assert _restricted_eval_in_subprocess("2 + 3") == 5

    def test_multiplication(self):
        assert _restricted_eval_in_subprocess("4 * 5") == 20

    def test_division(self):
        assert _restricted_eval_in_subprocess("10 / 4") == 2.5

    def test_power(self):
        assert _restricted_eval_in_subprocess("2 ** 8") == 256

    def test_floor_div(self):
        assert _restricted_eval_in_subprocess("10 // 3") == 3

    def test_modulo(self):
        assert _restricted_eval_in_subprocess("10 % 3") == 1

    def test_unary_minus(self):
        assert _restricted_eval_in_subprocess("-5 + 3") == -2

    def test_unsafe_expression_fails(self):
        with pytest.raises(RuntimeError):
            _restricted_eval_in_subprocess("__import__('os')")


class TestWASMSandbox:
    def test_health_info(self):
        box = WASMSandbox()
        h = box.health()
        assert "wasmtime_available" in h
        assert "engine_initialized" in h

    def test_eval_simple(self):
        box = WASMSandbox()
        result = box.eval("2 + 3")
        assert result == 5

    def test_eval_complex(self):
        box = WASMSandbox()
        result = box.eval("(1 + 2) * (3 + 4)")
        assert result == 21

    def test_eval_with_spaces(self):
        box = WASMSandbox()
        result = box.eval("  10   -   3  ")
        assert result == 7

    def test_eval_invalid_raises(self):
        box = WASMSandbox()
        with pytest.raises(ValueError):
            box.eval("eval('1')")

    def test_sandbox_eval_global(self):
        result = sandbox_eval("100 / 4")
        assert result == 25.0
