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
