"""Unit tests for :class:`uar.core.registry.SkillRegistry`.

Includes a regression for the previous ``@lru_cache`` bug where
``registry.list()`` would return a stale snapshot after the first call.
"""

from __future__ import annotations

import threading

import pytest

from uar.core.exceptions import SkillNotFoundError, ValidationError
from uar.core.registry import SkillRegistry


def test_register_and_get_returns_callable():
    reg = SkillRegistry()
    reg.register("alpha", lambda ctx: "ok")
    assert reg.is_registered("alpha")
    assert reg.get("alpha")(None) == "ok"


def test_register_rejects_invalid_name_or_function():
    reg = SkillRegistry()
    with pytest.raises(ValidationError):
        reg.register("", lambda ctx: None)
    with pytest.raises(ValidationError):
        reg.register("ok", "not callable")  # type: ignore[arg-type]


def test_register_rejects_duplicate():
    reg = SkillRegistry()
    reg.register("alpha", lambda ctx: None)
    with pytest.raises(ValidationError):
        reg.register("alpha", lambda ctx: None)


def test_get_unknown_skill_raises_skill_not_found():
    reg = SkillRegistry()
    with pytest.raises(SkillNotFoundError):
        reg.get("ghost")


def test_list_reflects_subsequent_registrations():
    """Regression: ``registry.list()`` must not be cached."""
    reg = SkillRegistry()
    reg.register("alpha", lambda ctx: None)
    first = reg.list()
    assert first == ["alpha"]

    reg.register("beta", lambda ctx: None)
    second = reg.list()

    assert "beta" in second
    assert sorted(second) == ["alpha", "beta"]


def test_list_returns_independent_snapshot():
    reg = SkillRegistry()
    reg.register("alpha", lambda ctx: None)
    snapshot = reg.list()
    snapshot.append("manipulated")
    assert "manipulated" not in reg.list()


def test_concurrent_register_and_list_is_safe():
    reg = SkillRegistry()
    errors: list[BaseException] = []

    def worker(prefix: str, n: int) -> None:
        try:
            for i in range(n):
                reg.register(f"{prefix}_{i}", lambda ctx, _i=i: _i)
                reg.list()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("a", 25)),
        threading.Thread(target=worker, args=("b", 25)),
        threading.Thread(target=worker, args=("c", 25)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(reg.list()) == 75


def test_search_by_prefix():
    reg = SkillRegistry()
    reg.register("math_add", lambda ctx: None)
    reg.register("math_sub", lambda ctx: None)
    reg.register("graph_query", lambda ctx: None)
    assert reg.search_by_prefix("math") == ["math_add", "math_sub"]
    assert reg.search_by_prefix("xyz") == []


def test_lazy_load_module_path():
    reg = SkillRegistry()
    reg.register("json_loads", "json:loads")
    fn = reg.get("json_loads")
    assert fn is not None
    assert fn('"hello"') == "hello"


def test_lazy_load_module_unresolvable():
    reg = SkillRegistry()
    reg.register("os_getcwd", "os")
    with pytest.raises(SkillNotFoundError):
        reg.get("os_getcwd")


def test_lazy_load_invalid_module():
    reg = SkillRegistry()
    reg.register("bad_mod", "definitely_not_a_module_12345")
    with pytest.raises(SkillNotFoundError):
        reg.get("bad_mod")


def test_lazy_load_plugins_no_crash():
    reg = SkillRegistry()
    reg._lazy_load_plugins()  # must not raise


def test_register_skill_decorator():
    from uar.core.registry import register_skill

    @register_skill("test_dec_skill")
    def my_skill(ctx):
        return {"status": "ok"}

    from uar.core.registry import registry

    assert registry.is_registered("test_dec_skill")


def test_requires_package_missing():
    from uar.core.registry import requires_package

    @requires_package("definitely_not_a_pkg_12345")
    def my_skill(ctx):
        return {"status": "ok"}

    result = my_skill(None)
    assert result["status"] == "failed"
    assert "not installed" in result["error"]


def test_requires_package_present():
    from uar.core.registry import requires_package

    @requires_package("json")
    def my_skill(ctx):
        return {"status": "ok"}

    assert my_skill(None) == {"status": "ok"}


def test_session_lifecycle():
    reg = SkillRegistry()
    s1 = reg._get_session()
    s2 = reg._get_session()
    assert s1 is s2
    reg._close_session()
    assert reg._session is None


def test_lazy_register_path_validation():
    reg = SkillRegistry()
    with pytest.raises(ValidationError):
        reg.register("x", "  ")
    with pytest.raises(ValidationError):
        reg.register("x", "has spaces")
