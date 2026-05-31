"""Tests for uar.core.scheduler DAG scheduling."""

import pytest

from uar.core.registry import SkillRegistry, register_skill
from uar.core.scheduler import (
    CircularDependencyError,
    schedule,
)


# Register some test skills with metadata
@register_skill("reader_a", reads=["x"], writes=["a"])
def _reader_a(ctx):
    return {}


@register_skill("reader_b", reads=["y"], writes=["b"])
def _reader_b(ctx):
    return {}


@register_skill("writer_x", writes=["x"])
def _writer_x(ctx):
    return {}


@register_skill("writer_y", writes=["y"])
def _writer_y(ctx):
    return {}


@register_skill("consumer_ab", reads=["a", "b"], writes=["c"])
def _consumer_ab(ctx):
    return {}


@register_skill("noop_skill")
def _noop_skill(ctx):
    return {}


class TestDAGScheduler:
    def test_sequential_when_no_dependencies(self):
        """Independent skills can run in a single wave."""
        reg = SkillRegistry()
        reg.register("s1", _noop_skill, metadata={"writes": ["s1"]})
        reg.register("s2", _noop_skill, metadata={"writes": ["s2"]})
        reg.register("s3", _noop_skill, metadata={"writes": ["s3"]})
        waves = schedule(["s1", "s2", "s3"], reg)
        assert len(waves) == 1
        assert set(waves[0]) == {"s1", "s2", "s3"}

    def test_read_after_write_creates_dependency(self):
        """A skill that reads key X must wait for the skill that writes X."""
        reg = SkillRegistry()
        reg.register("producer", _noop_skill, metadata={"writes": ["data"]})
        reg.register("consumer", _noop_skill, metadata={"reads": ["data"]})
        waves = schedule(["producer", "consumer"], reg)
        assert len(waves) == 2
        assert waves[0] == ["producer"]
        assert waves[1] == ["consumer"]

    def test_multiple_independent_producers_same_wave(self):
        """Multiple producers of different keys run in parallel."""
        reg = SkillRegistry()
        reg.register("px", _noop_skill, metadata={"writes": ["x"]})
        reg.register("py", _noop_skill, metadata={"writes": ["y"]})
        reg.register("c", _noop_skill, metadata={"reads": ["x", "y"]})
        waves = schedule(["px", "py", "c"], reg)
        assert len(waves) == 2
        assert set(waves[0]) == {"px", "py"}
        assert waves[1] == ["c"]

    def test_explicit_dependencies_override(self):
        """explicit_deps can force ordering even without read/write."""
        reg = SkillRegistry()
        reg.register("a", _noop_skill, metadata={"writes": ["a"]})
        reg.register("b", _noop_skill, metadata={"writes": ["b"]})
        waves = schedule(
            ["b", "a"], reg, explicit_deps={"a": ["b"]}
        )
        assert len(waves) == 2
        assert waves[0] == ["b"]
        assert waves[1] == ["a"]

    def test_context_modifying_skill_serializes(self):
        """Context-modifying skills force all prior skills to
        complete first."""
        reg = SkillRegistry()
        reg.register("before", _noop_skill, metadata={"writes": ["before"]})
        reg.register("doc_ingest", _noop_skill, metadata={"writes": ["text"]})
        reg.register("after", _noop_skill, metadata={"reads": ["text"]})
        waves = schedule(["before", "doc_ingest", "after"], reg)
        # doc_ingest depends on before; after depends on doc_ingest
        assert len(waves) == 3
        assert waves[0] == ["before"]
        assert waves[1] == ["doc_ingest"]
        assert waves[2] == ["after"]

    def test_empty_skill_list(self):
        waves = schedule([], SkillRegistry())
        assert waves == []

    def test_circular_dependency_raises(self):
        """Cycles in explicit dependencies must raise
        CircularDependencyError."""
        reg = SkillRegistry()
        reg.register("a", _noop_skill, metadata={"writes": ["a"]})
        reg.register("b", _noop_skill, metadata={"writes": ["b"]})
        with pytest.raises(CircularDependencyError):
            schedule(
                ["a", "b"], reg, explicit_deps={"a": ["b"], "b": ["a"]}
            )

    def test_diamond_dependency(self):
        """Diamond DAG: A -> B, A -> C, B,C -> D. B and C run in parallel."""
        reg = SkillRegistry()
        reg.register("a", _noop_skill, metadata={"writes": ["x"]})
        reg.register("b", _noop_skill, metadata={
            "reads": ["x"], "writes": ["y"],
        })
        reg.register("c", _noop_skill, metadata={
            "reads": ["x"], "writes": ["z"],
        })
        reg.register("d", _noop_skill, metadata={"reads": ["y", "z"]})
        waves = schedule(["a", "b", "c", "d"], reg)
        assert len(waves) == 3
        assert waves[0] == ["a"]
        assert set(waves[1]) == {"b", "c"}
        assert waves[2] == ["d"]
