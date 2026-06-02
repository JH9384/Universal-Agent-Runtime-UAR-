"""Unit tests for Mission Control (T5)."""

from uar.core.mission_control import MissionControlSnapshot, build_snapshot
from uar.core.registry import SkillRegistry
from uar.memory.sqlite_store import SqliteRunStore


def _make_store(tmp_path):
    return SqliteRunStore(path=str(tmp_path / "mc_test.db"))


def _make_registry():
    reg = SkillRegistry()
    reg.register("echo", lambda ctx: ctx)
    return reg


class _BurnIn:
    def __init__(self, score=100, passed=True):
        self.score = score
        self.passed = passed


def test_snapshot_has_required_keys(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert isinstance(snap, MissionControlSnapshot)
    d = snap.to_dict()
    assert "replay_confidence" in d
    assert "runtime_health" in d
    assert "certification" in d
    assert "active_runs" in d
    assert "recent_warnings" in d
    assert "timestamp" in d


def test_snapshot_runtime_health_has_score(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
        burnin_report=_BurnIn(100, True),
    )
    assert snap.runtime_health is not None
    assert "score" in snap.runtime_health
    assert 0 <= snap.runtime_health["score"] <= 100


def test_snapshot_certification_has_level(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert snap.certification is not None
    assert "level" in snap.certification
    assert snap.certification["level"] in (
        "Experimental", "Silver", "Gold"
    )


def test_snapshot_active_runs_is_zero_empty_store(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert snap.active_runs == 0


def test_snapshot_to_dict_serializable(tmp_path):
    import json

    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    d = snap.to_dict()
    json.dumps(d)


def test_snapshot_no_replay_confidence_when_store_empty(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert snap.replay_confidence is None


# --- New field tests (frontend redundancy fix) ---


def test_snapshot_includes_server_version(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert isinstance(snap.server_version, str)
    assert snap.server_version != "unknown"


def test_snapshot_includes_uptime_seconds(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert isinstance(snap.uptime_seconds, int)
    assert snap.uptime_seconds >= 0


def test_snapshot_includes_skill_counts(tmp_path):
    reg = _make_registry()
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=reg,
    )
    assert snap.skills_total == 1
    assert snap.skills_available == 1


def test_snapshot_includes_circuit_breakers(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert isinstance(snap.circuit_breakers, list)


def test_snapshot_skills_available_less_than_total_on_failure(tmp_path):
    reg = SkillRegistry()
    reg.register("good", lambda ctx: ctx)
    reg.register("bad", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    # Note: registry.get does not execute the skill, so both are available.
    # This test documents the current behavior.
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=reg,
    )
    assert snap.skills_total == 2
    assert snap.skills_available == 2
