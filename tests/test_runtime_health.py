"""Unit tests for the Runtime Health scoring module (T2)."""

from uar.core.registry import SkillRegistry
from uar.core.runtime_health import (
    ComponentHealth,
    RuntimeHealthReport,
    health_tier,
    score_runtime_health,
)
from uar.memory.sqlite_store import SqliteRunStore


def _make_store(tmp_path):
    return SqliteRunStore(path=str(tmp_path / "rh_test.db"))


def _make_registry(*skill_names):
    reg = SkillRegistry()
    for name in skill_names:
        reg.register(name, lambda ctx: ctx)
    return reg


class _FakeBurnIn:
    def __init__(self, score=100, passed=True):
        self.score = score
        self.passed = passed


def test_health_tier_boundaries():
    assert health_tier(100) == "Nominal"
    assert health_tier(95) == "Nominal"
    assert health_tier(94) == "Healthy"
    assert health_tier(75) == "Healthy"
    assert health_tier(74) == "Degraded"
    assert health_tier(50) == "Degraded"
    assert health_tier(49) == "Unstable"
    assert health_tier(25) == "Unstable"
    assert health_tier(24) == "Critical"
    assert health_tier(0) == "Critical"


def test_report_has_required_structure(tmp_path):
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("echo"),
    )
    assert isinstance(report, RuntimeHealthReport)
    assert 0 <= report.score <= 100
    assert report.tier in (
        "Nominal", "Healthy", "Degraded", "Unstable", "Critical"
    )
    assert isinstance(report.components, dict)
    assert isinstance(report.warnings, list)
    assert isinstance(report.timestamp, float)


def test_report_to_dict_shape(tmp_path):
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("echo"),
    )
    d = report.to_dict()
    assert "score" in d
    assert "tier" in d
    assert "components" in d
    assert "warnings" in d
    assert "timestamp" in d
    for comp_name in ("execution", "skills", "events",
                      "streaming", "pressure"):
        assert comp_name in d["components"]
        assert "score" in d["components"][comp_name]
        assert "status" in d["components"][comp_name]


def test_empty_store_scores_high(tmp_path, monkeypatch):
    import uar.core.runtime_health as _rh
    monkeypatch.setattr(_rh, "_get_circuit_states", lambda: {})
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("echo", "math"),
        burnin_report=_FakeBurnIn(score=100, passed=True),
    )
    assert report.score >= 75
    assert report.tier in ("Nominal", "Healthy")


def test_registry_with_skills_scores_skills_nominal(tmp_path, monkeypatch):
    import uar.core.runtime_health as _rh
    monkeypatch.setattr(_rh, "_get_circuit_states", lambda: {})
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("a", "b", "c"),
    )
    skills_component = report.components["skills"]
    assert skills_component.score >= 80


def test_empty_registry_degrades_skills_score(tmp_path):
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    skills_component = report.components["skills"]
    assert skills_component.score <= 60
    assert any("skills" in w for w in report.warnings)


def test_failed_burnin_degrades_pressure(tmp_path):
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("echo"),
        burnin_report=_FakeBurnIn(score=20, passed=False),
    )
    pressure = report.components["pressure"]
    assert pressure.score < 80
    assert any("pressure" in w for w in report.warnings)


def test_none_burnin_returns_unknown_pressure(tmp_path):
    report = score_runtime_health(
        store=_make_store(tmp_path),
        registry=_make_registry("echo"),
        burnin_report=None,
    )
    assert report.components["pressure"].status == "unknown"
    assert report.components["pressure"].score == 75


def test_component_health_dataclass():
    ch = ComponentHealth(score=90, status="healthy", notes=["ok"])
    assert ch.score == 90
    assert ch.status == "healthy"
    assert ch.notes == ["ok"]
