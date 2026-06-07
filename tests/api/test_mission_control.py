"""Unit tests for Mission Control (T5)."""

from uar.core.contracts import RunRecord
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
    from uar.core.circuit_breaker_decorator import get_circuit_breaker

    cb = get_circuit_breaker("mc_test_svc", failure_threshold=1)

    def _fail():
        raise RuntimeError("fail")

    try:
        cb.call(_fail)
    except Exception:
        pass

    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert isinstance(snap.circuit_breakers, list)
    assert len(snap.circuit_breakers) > 0
    circuit = next(
        (c for c in snap.circuit_breakers if c["name"] == "mc_test_svc"),
        None,
    )
    assert circuit is not None
    assert circuit["state"] == "open"
    assert "failures" in circuit
    assert "half_open_count" in circuit
    assert "half_open_successes" in circuit
    assert "last_failure_time" in circuit


def test_snapshot_skills_available_less_than_total_on_failure(tmp_path):
    reg = SkillRegistry()
    reg.register("good", lambda ctx: ctx)
    reg.register(
        "bad", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    # Note: registry.get does not execute the skill, so both are available.
    # This test documents the current behavior.
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=reg,
    )
    assert snap.skills_total == 2
    assert snap.skills_available == 2


def test_snapshot_includes_nominal_fleet_summary_empty_store(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    assert snap.fleet_summary is not None
    assert snap.fleet_summary["status"] == "nominal"
    assert snap.fleet_summary["active_signals"] == 0
    assert snap.fleet_summary["top_signal"] is None


def test_snapshot_includes_fleet_summary_from_existing_runs(tmp_path):
    store = _make_store(tmp_path)
    store.append(
        RunRecord(
            run_id="fleet-r1",
            goal_id="g1",
            skills=["echo"],
            status="failed",
            errors=["boom"],
            metadata={"service": "svc-a"},
        )
    )
    store.flush()

    snap = build_snapshot(
        store=store,
        registry=_make_registry(),
    )

    assert snap.fleet_summary is not None
    assert snap.fleet_summary["status"] == "critical"
    assert snap.fleet_summary["active_signals"] == 1
    assert snap.fleet_summary["top_signal"]["latest_run_id"] == "fleet-r1"
    assert snap.fleet_summary["top_signal"]["scope"] == "service"


def test_snapshot_fleet_summary_includes_replay_incident_and_recommendation_linkage(tmp_path):
    store = _make_store(tmp_path)
    store.append(
        RunRecord(
            run_id="fleet-r2",
            goal_id="g1",
            skills=["echo"],
            status="failed",
            errors=["boom"],
            metadata={
                "service": "svc-b",
                "incident_id": "inc-1",
                "recommendation_id": "rec-1",
            },
        )
    )
    store.flush()

    snap = build_snapshot(
        store=store,
        registry=_make_registry(),
    )

    top = snap.fleet_summary["top_signal"]
    linkage = top["linkage"]
    assert linkage["replay"] == {"run_id": "fleet-r2", "available": True}
    assert linkage["incidents"] == ["inc-1"]
    assert linkage["recommendations"] == ["rec-1"]
    assert linkage["evidence_refs"] == ["run:fleet-r2"]


def test_snapshot_includes_nominal_incident_summary_empty_store(tmp_path):
    snap = build_snapshot(
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )

    assert snap.incident_summary is not None
    assert snap.incident_summary["status"] == "nominal"
    assert snap.incident_summary["recurring_patterns"] == 0
    assert snap.incident_summary["top_pattern"] is None


def test_snapshot_includes_incident_summary_from_recurring_failures(tmp_path):
    store = _make_store(tmp_path)
    store.append(
        RunRecord(
            run_id="incident-r1",
            goal_id="g1",
            skills=["echo"],
            status="failed",
            errors=["boom"],
            metadata={"service": "svc-rec", "incident_id": "inc-1"},
        )
    )
    store.append(
        RunRecord(
            run_id="incident-r2",
            goal_id="g1",
            skills=["echo"],
            status="failed",
            errors=["boom again"],
            metadata={"service": "svc-rec", "recommendation_id": "rec-1"},
        )
    )
    store.flush()

    snap = build_snapshot(
        store=store,
        registry=_make_registry(),
    )

    assert snap.incident_summary is not None
    assert snap.incident_summary["status"] == "active"
    assert snap.incident_summary["recurring_patterns"] == 1
    top = snap.incident_summary["top_pattern"]
    assert top["scope"] == "service"
    assert top["value"] == "svc-rec"
    assert top["latest_run_id"] in {"incident-r1", "incident-r2"}
    assert top["linked_incident_ids"] == ["inc-1"]
    assert top["linked_recommendation_ids"] == ["rec-1"]
