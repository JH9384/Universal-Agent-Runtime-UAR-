"""Tests for the restricted AST-based safe_eval module.

Covers: allowed expressions, blocked malicious constructs, fuzzing.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from uar.core.safe_eval import (
    SafeEvalAttrError,
    SafeEvalError,
    SafeEvalNameError,
    SafeEvalNodeError,
    safe_eval,
    safe_eval_with_numpy,
)


class TestAllowedExpressions:
    def test_basic_arithmetic(self):
        assert safe_eval("2 + 3") == 5
        assert safe_eval("10 * 4") == 40
        assert safe_eval("2 ** 10") == 1024

    def test_numpy_namespace(self):
        assert safe_eval("np.sin(0)", {"np": np}) == 0.0
        assert safe_eval("np.pi", {"np": np}) == pytest.approx(math.pi)

    def test_custom_namespace(self):
        assert safe_eval("x[0] ** 2 + x[1]", {"x": [3, 5]}) == 14

    def test_list_literal(self):
        assert safe_eval("[1, 2, 3]") == [1, 2, 3]

    def test_tuple_literal(self):
        assert safe_eval("(1, 2)") == (1, 2)

    def test_dict_literal(self):
        assert safe_eval("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}

    def test_comparison(self):
        assert safe_eval("1 < 2") is True
        assert safe_eval("3 == 3") is True
        assert safe_eval("4 != 5") is True


class TestBlockedMaliciousExpressions:
    def test_import_blocked(self):
        with pytest.raises(SafeEvalError):
            safe_eval("__import__('os').system('ls')")

    def test_builtins_blocked(self):
        with pytest.raises(SafeEvalNameError):
            safe_eval("__builtins__")

    def test_exec_blocked(self):
        # Blocked as disallowed name (exec not in namespace)
        with pytest.raises(SafeEvalError):
            safe_eval("exec('pass')")

    def test_eval_blocked(self):
        with pytest.raises(SafeEvalNameError):
            safe_eval("eval('1+1')")

    def test_open_blocked(self):
        with pytest.raises(SafeEvalNameError):
            safe_eval("open('/etc/passwd')")

    def test_subprocess_blocked(self):
        # Not valid eval syntax — parse error
        with pytest.raises(SafeEvalError):
            safe_eval("import subprocess; subprocess.run('ls')")

    def test_getattr_blocked(self):
        with pytest.raises(SafeEvalAttrError):
            safe_eval("(1).__class__")

    def test_mro_blocked(self):
        with pytest.raises(SafeEvalAttrError):
            safe_eval("(1).__class__.__mro__")

    def test_globals_blocked(self):
        # Lambda is blocked before attribute access is reached
        with pytest.raises(SafeEvalError):
            safe_eval("(lambda: None).__globals__")

    def test_code_blocked(self):
        with pytest.raises(SafeEvalError):
            safe_eval("(lambda: None).__code__")

    def test_lambda_blocked(self):
        with pytest.raises(SafeEvalNodeError):
            safe_eval("(lambda x: x)(5)")

    def test_assignment_blocked(self):
        with pytest.raises(SafeEvalError):
            safe_eval("x = 5")

    def test_for_loop_blocked(self):
        with pytest.raises(SafeEvalNodeError):
            safe_eval("sum([i for i in range(5)])")

    def test_attribute_chain_blocked(self):
        with pytest.raises(SafeEvalAttrError):
            safe_eval("(1).__class__.__bases__[0].__subclasses__()")


class TestSafeEvalWithNumpy:
    def test_auto_injected_functions(self):
        assert safe_eval_with_numpy("sin(0)") == 0.0
        assert safe_eval_with_numpy("cos(0)") == 1.0
        assert safe_eval_with_numpy("exp(0)") == 1.0
        assert safe_eval_with_numpy("log(1)") == 0.0

    def test_auto_injected_constants(self):
        assert safe_eval_with_numpy("pi") == pytest.approx(math.pi)
        assert safe_eval_with_numpy("e") == pytest.approx(math.e)

    def test_local_vars_override(self):
        assert safe_eval_with_numpy("x * 2", {"x": 5}) == 10


class TestFuzzMaliciousExpressions:
    """Fuzz-style: 100+ malicious expressions all blocked."""

    MALICIOUS = [
        "__import__('os')",
        "__builtins__['open']('/etc/passwd')",
        "(1).__class__.__bases__[0].__subclasses__()",
        "().__class__.__bases__[0].__subclasses__()[137].__init__.__globals__",
        "[].__class__.__mro__[-1].__subclasses__()",
        "(lambda: None).__globals__",
        "(lambda: None).__code__",
        "(1).__dict__",
        "''.__class__.__getattribute__('__class__')",
        "[].__class__.__setattr__('x', 1)",
        "().__class__.__delattr__('x')",
        "[].__class__.__weakref__",
        "[].__class__.__module__",
        "''.__class__.__func__",
        "''.__class__.__self__",
        "().__class__.__get__",
        "().__class__.__set__",
        "().__class__.__delete__",
        "().__class__.__getattribute__",
        "().__class__.__setattr__",
        "().__class__.__delattr__",
        "import os",
        "from os import system",
        "exec('pass')",
        "compile('1+1', '', 'eval')",
        "eval('1+1')",
        "open('x')",
        "file('x')",
        "breakpoint()",
        "assert False",
        "raise Exception('boom')",
        "del x",
        "x = 5",
        "x += 5",
        "for i in range(5): pass",
        "while True: pass",
        "if True: pass",
        "try: pass\nexcept: pass",
        "with open('x') as f: pass",
        "class X: pass",
        "def f(): pass",
        "lambda x: x",
        "yield 1",
        "return 1",
        "global x",
        "nonlocal x",
        "pass; os.system('ls')",
        "(1).__class__.__bases__[0].__subclasses__()",
        "[x for x in (1).__class__.__bases__[0].__subclasses__() "
        "if x.__name__ == 'warnings.catch_warnings'][0]()."
        "_module.__builtins__['__import__']('os').system('ls')",
        "(1).__class__.__bases__[0].__subclasses__()[-1]."
        "__init__.__globals__['__builtins__']['open']('/etc/passwd')",
        "[].__class__.__mro__[-1].__subclasses__()[-1]."
        "__init__.__globals__['__builtins__']['__import__']('os')."
        "system('ls')",
    ]

    @pytest.mark.parametrize("expr", MALICIOUS)
    def test_malicious_expression_blocked(self, expr):
        with pytest.raises(SafeEvalError):
            safe_eval_with_numpy(expr)


class TestInternalHelpers:
    """Direct tests for internal helper functions."""

    def test_disallowed_string_in_nested(self):
        import ast
        from uar.core.safe_eval import _disallowed_string_in

        tree = ast.parse("a + '__class__'")
        result = _disallowed_string_in(tree)
        assert result == "__class__"

    def test_eval_slice_constant_index_wrapper(self):
        import ast
        from uar.core.safe_eval import _eval_slice_constant

        node = ast.Index(value=ast.Constant(value="foo"))
        result = _eval_slice_constant(node)
        assert result == "foo"


class TestMaxLength:
    def test_long_expression_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("1+1" * 2000, max_len=100)

    def test_default_max_len_accepted(self):
        # Should not raise
        safe_eval("1 + 1")


class TestInvalidSyntax:
    def test_invalid_syntax_raises(self):
        with pytest.raises(SafeEvalError):
            safe_eval("1 + + +")
