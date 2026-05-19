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
