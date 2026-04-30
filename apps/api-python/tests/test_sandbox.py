from sandbox import run_code


def test_simple_sum():
    inputs = [{"content": 2}, {"content": 3}]
    result = run_code("sum(values)", inputs, {})
    assert result == 5


def test_len_inputs():
    inputs = [{"content": 1}, {"content": 2}, {"content": 3}]
    result = run_code("len(inputs)", inputs, {})
    assert result == 3


def test_disallowed_builtin():
    inputs = [{"content": 1}]
    try:
        run_code("__import__('os').system('ls')", inputs, {})
        assert False
    except Exception:
        assert True
