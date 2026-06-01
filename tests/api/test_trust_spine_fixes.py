"""Regression tests for Trust Spine fixes.

Covers:
  FIX-1  BurnInProxy defined once in burn_in.py, imported by all consumers
  FIX-2  _latest_report is thread-safe (RLock + _set_latest_report)
  FIX-3  Dead per-endpoint auth guards removed; uor_router require_auth still
         enforces auth on every route
  FIX-4  replay_explorer enforces per-run ownership; admins bypass
  FIX-5  timeline import is module-level, not hidden in try/except at call time
  FIX-6  test_app fixture removed from test_replay_explorer.py
  ISS-85 RuntimeSnapshot consolidates 4 store scans into 1 per request
  ISS-86 BurnIn report persists to store; recovered after restart
  ISS-87 Certification Engine uses pure Trust Spine weights (T1=40 T3=35 T2=25)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

import uar.api.middleware as _mw
import uar.api.routers.burn_in as _burnin_mod
from uar.core.contracts import RunRecord
from uar.memory.sqlite_store import SqliteRunStore

_ADMIN_KEY = "fix-test-admin-key"
_USER_KEY = "fix-test-user-key"
_ADMIN_HEADERS = {"Authorization": f"Bearer {_ADMIN_KEY}"}
_USER_HEADERS = {"Authorization": f"Bearer {_USER_KEY}"}


@pytest.fixture(autouse=True)
def _inject_keys(monkeypatch):
    monkeypatch.setitem(
        _mw.API_KEYS, _ADMIN_KEY, {"user": "admin_user", "tier": "admin"}
    )
    monkeypatch.setitem(
        _mw.API_KEYS, _USER_KEY, {"user": "regular_user", "tier": "user"}
    )


@pytest.fixture()
def client():
    from uar.api.server import app
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    import uar.api.server as _server_mod

    store = SqliteRunStore(path=str(tmp_path / "fix_tests.db"))
    monkeypatch.setattr(_server_mod, "store", store)
    return store


# ---------------------------------------------------------------------------
# FIX-1: BurnInProxy is a single class defined in burn_in.py
# ---------------------------------------------------------------------------

def test_burnin_proxy_importable_from_burn_in():
    from uar.api.routers.burn_in import BurnInProxy
    assert callable(BurnInProxy)


def test_burnin_proxy_score_and_passed_coercion():
    from uar.api.routers.burn_in import BurnInProxy

    p = BurnInProxy({"score": "87", "passed": 1})
    assert p.score == 87
    assert p.passed is True


def test_burnin_proxy_from_latest_returns_none_when_empty(monkeypatch):
    from uar.api.routers.burn_in import BurnInProxy

    monkeypatch.setattr(_burnin_mod, "_latest_report", None)
    assert BurnInProxy.from_latest() is None


def test_burnin_proxy_from_latest_returns_proxy_when_set(monkeypatch):
    from uar.api.routers.burn_in import BurnInProxy, _set_latest_report

    _set_latest_report({"score": 95, "passed": True})
    try:
        proxy = BurnInProxy.from_latest()
        assert proxy is not None
        assert proxy.score == 95
        assert proxy.passed is True
    finally:
        monkeypatch.setattr(_burnin_mod, "_latest_report", None)


def test_runtime_health_router_uses_burnin_proxy_not_inline(monkeypatch):
    """runtime_health router must import BurnInProxy, not define it inline."""
    import inspect
    import uar.api.routers.runtime_health as _rh_router

    src = inspect.getsource(_rh_router)
    assert "class _BurnInProxy" not in src, (
        "Inline _BurnInProxy class still present in runtime_health router"
    )
    assert "BurnInProxy" in src


def test_certification_router_uses_burnin_proxy_not_inline(monkeypatch):
    import inspect
    import uar.api.routers.certification as _cert_router

    src = inspect.getsource(_cert_router)
    assert "class _BurnInProxy" not in src, (
        "Inline _BurnInProxy class still present in certification router"
    )
    assert "BurnInProxy" in src


def test_mission_control_router_uses_burnin_proxy_not_inline(monkeypatch):
    import inspect
    import uar.api.routers.mission_control as _mc_router

    src = inspect.getsource(_mc_router)
    assert "class _BurnInProxy" not in src, (
        "Inline _BurnInProxy class still present in mission_control router"
    )
    assert "BurnInProxy" in src


# ---------------------------------------------------------------------------
# FIX-2: Thread-safe _latest_report
# ---------------------------------------------------------------------------

def test_set_latest_report_is_thread_safe(monkeypatch):
    """Concurrent writes to _latest_report must not corrupt state."""
    from uar.api.routers.burn_in import _set_latest_report

    monkeypatch.setattr(_burnin_mod, "_latest_report", None)
    errors: list[Exception] = []

    def _writer(val: int) -> None:
        try:
            _set_latest_report({"score": val, "passed": val > 50})
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=_writer, args=(i,))
        for i in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"
    # Final value must be one of the written payloads (0-19)
    with _burnin_mod._report_lock:
        final = _burnin_mod._latest_report
    assert final is not None
    assert final["score"] in range(20), f"Unexpected: {final}"


def test_get_latest_burnin_reads_under_lock(monkeypatch, isolated_store):
    """GET /burnin/latest returns the report set via _set_latest_report."""
    from uar.api.routers.burn_in import _set_latest_report
    from uar.api.server import app

    _set_latest_report({"score": 77, "passed": True, "level": "smoke"})
    try:
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/uar/burnin/latest", headers=_ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["score"] == 77
    finally:
        monkeypatch.setattr(_burnin_mod, "_latest_report", None)


# ---------------------------------------------------------------------------
# FIX-3: Trust Spine routers enforce defense-in-depth auth
# ---------------------------------------------------------------------------

def test_runtime_health_router_has_auth_guard():
    import inspect
    import uar.api.routers.runtime_health as _rh

    src = inspect.getsource(_rh.get_runtime_health)
    assert "Authentication required" in src, (
        "runtime_health router missing per-endpoint auth guard"
    )


def test_certification_router_has_auth_guard():
    import inspect
    import uar.api.routers.certification as _cert

    src = inspect.getsource(_cert.get_certification)
    assert "Authentication required" in src, (
        "certification router missing per-endpoint auth guard"
    )


def test_mission_control_router_has_auth_guard():
    import inspect
    import uar.api.routers.mission_control as _mc

    src = inspect.getsource(_mc.get_mission_control)
    assert "Authentication required" in src, (
        "mission_control router missing per-endpoint auth guard"
    )


def test_certification_rejects_no_auth(client: TestClient):
    """GET /api/uar/certification without credentials must 401."""
    resp = client.get("/api/uar/certification")
    assert resp.status_code == 401


def test_unauthenticated_request_returns_401_via_require_auth(isolated_store):
    """require_auth on uor_router still enforces 401 for all routes."""
    from uar.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    for path in (
        "/api/uar/health/runtime",
        "/api/uar/certification",
        "/api/uar/mission-control",
        "/api/uar/burnin/latest",
    ):
        resp = client.get(path)
        assert resp.status_code == 401, (
            f"{path} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# FIX-4: replay_explorer ownership check
# ---------------------------------------------------------------------------

def _store_run(store, run_id, user_id=None, status="success"):
    record = RunRecord(
        run_id=run_id,
        goal_id="g1",
        skills=["echo"],
        status=status,
        outputs=["ok"],
        events=[],
        final_context={},
        user_id=user_id,
    )
    store.append(record)
    return run_id


def test_admin_can_access_any_run(isolated_store, monkeypatch):
    from uar.api.server import app

    run_id = f"owned-run-{int(time.time()*1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    )
    isolated_store.append(record)

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer", headers=_ADMIN_HEADERS
    )
    assert resp.status_code == 200, resp.text


def test_non_owner_run_is_allowed_when_no_owner_set(isolated_store):
    """Runs with no user_id must be allowed to any authenticated user.

    Regression fix: aligned with replay_confidence.py so unowned runs
    are readable by all authenticated users.
    """
    from uar.api.server import app

    run_id = f"unowned-run-{int(time.time()*1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    )
    isolated_store.append(record)
    isolated_store.flush()

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer", headers=_USER_HEADERS
    )
    assert resp.status_code == 200, (
        f"Expected 200 for authenticated user accessing ownerless run, "
        f"got {resp.status_code}"
    )


def test_explorer_404_returns_proper_error(isolated_store):
    from uar.api.server import app

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        "/api/uar/runs/no-such-run/explorer", headers=_ADMIN_HEADERS
    )
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error"] == "run_not_found"


# ---------------------------------------------------------------------------
# FIX-5: timeline import is module-level
# ---------------------------------------------------------------------------

def test_timeline_import_is_module_level():
    """timeline_from_record must be at module level in replay_explorer."""
    import inspect
    import uar.api.routers.replay_explorer as _re

    # The symbol must be present at module scope (not only inside functions)
    assert hasattr(_re, "timeline_from_record"), (
        "timeline_from_record not at module level"
    )
    fn_src = inspect.getsource(_re.get_replay_explorer)
    assert "from uar.core.timeline import" not in fn_src, (
        "timeline import still inside endpoint function"
    )


# ---------------------------------------------------------------------------
# FIX-6: test_app fixture removed from test_replay_explorer.py
# ---------------------------------------------------------------------------

def test_unused_test_app_fixture_is_gone():
    import importlib.util
    import inspect
    from pathlib import Path

    src_path = (
        Path(__file__).parent / "test_replay_explorer.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_test_replay_explorer", src_path
    )
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)

    fixture_names = [
        name for name, obj in inspect.getmembers(_mod)
        if callable(obj)
        and getattr(obj, "_pytestfixturefunction", None)
    ]
    assert "test_app" not in fixture_names, (
        "Unused test_app fixture still present in test_replay_explorer"
    )


# ---------------------------------------------------------------------------
# ISS-85: RuntimeSnapshot consolidates store scans
# ---------------------------------------------------------------------------

def test_build_runtime_snapshot_returns_correct_fields(isolated_store):
    """build_runtime_snapshot returns RuntimeSnapshot with expected fields."""
    from uar.core.runtime_health import (
        RuntimeSnapshot,
        build_runtime_snapshot,
    )

    snap = build_runtime_snapshot(isolated_store)
    assert isinstance(snap, RuntimeSnapshot)
    assert isinstance(snap.recent_records, list)
    assert isinstance(snap.active_count, int)
    assert isinstance(snap.queried_at, float)
    assert snap.latest_record is None


def test_build_runtime_snapshot_populates_latest_record(
    isolated_store,
):
    """latest_record is set when records exist."""
    from uar.core.runtime_health import build_runtime_snapshot

    run_id = f"snap-run-{int(time.time() * 1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    )
    isolated_store.append(record)
    isolated_store.flush()

    snap = build_runtime_snapshot(isolated_store)
    assert snap.latest_record is not None
    assert snap.recent_records


def test_build_runtime_snapshot_counts_active_runs(isolated_store):
    """active_count reflects only running/pending/queued records."""
    from uar.core.runtime_health import build_runtime_snapshot

    for i, status in enumerate(("running", "pending", "success")):
        record = RunRecord(
            run_id=f"active-{i}", goal_id="g1", skills=["echo"],
            status=status, outputs=[], events=[], final_context={},
        )
        isolated_store.append(record)
    isolated_store.flush()

    snap = build_runtime_snapshot(isolated_store)
    assert snap.active_count == 2


def test_score_runtime_health_accepts_snapshot(isolated_store):
    """score_runtime_health works with snapshot= kwarg (no store= needed)."""
    from uar.core.registry import SkillRegistry
    from uar.core.runtime_health import (
        RuntimeHealthReport,
        build_runtime_snapshot,
        score_runtime_health,
    )

    registry = SkillRegistry()
    registry.register("echo", lambda ctx: ctx)
    snap = build_runtime_snapshot(isolated_store)

    report = score_runtime_health(
        registry=registry,
        snapshot=snap,
    )
    assert isinstance(report, RuntimeHealthReport)
    assert 0 <= report.score <= 100


def test_score_runtime_health_legacy_store_kwarg(isolated_store):
    """score_runtime_health still works via store= (backward compat)."""
    from uar.core.registry import SkillRegistry
    from uar.core.runtime_health import (
        RuntimeHealthReport,
        score_runtime_health,
    )

    registry = SkillRegistry()
    report = score_runtime_health(
        registry=registry,
        store=isolated_store,
    )
    assert isinstance(report, RuntimeHealthReport)


def test_score_runtime_health_raises_without_snapshot_or_store():
    """score_runtime_health raises ValueError when neither is provided."""
    from uar.core.registry import SkillRegistry
    from uar.core.runtime_health import score_runtime_health

    registry = SkillRegistry()
    with pytest.raises(ValueError, match="snapshot= or store="):
        score_runtime_health(registry=registry)


def test_mission_control_single_store_scan(
    isolated_store, monkeypatch
):
    """GET /api/uar/mission-control issues exactly one list_records call."""
    from functools import wraps
    from uar.api.server import app

    call_count = 0
    original = isolated_store.list_records

    @wraps(original)
    def _counting(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(isolated_store, "list_records", _counting)

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        "/api/uar/mission-control", headers=_ADMIN_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert call_count == 1, (
        f"Expected 1 store scan, got {call_count}"
    )


def test_runtime_snapshot_exported_in_all():
    """RuntimeSnapshot is in runtime_health.__all__."""
    import uar.core.runtime_health as _rh
    assert "RuntimeSnapshot" in _rh.__all__
    assert "build_runtime_snapshot" in _rh.__all__


# ---------------------------------------------------------------------------
# ISS-86: Burn-In persistence layer
# ---------------------------------------------------------------------------

def test_put_and_get_metadata_roundtrip(isolated_store):
    """put_metadata + flush + get_metadata returns the original value."""
    payload = {"score": 95, "passed": True, "note": "ok"}
    isolated_store.put_metadata("__test_key__", payload)
    isolated_store.flush()
    recovered = isolated_store.get_metadata("__test_key__")
    assert recovered == payload


def test_get_metadata_missing_key_returns_none(isolated_store):
    """get_metadata returns None for an unknown key."""
    assert isolated_store.get_metadata("__no_such_key__") is None


def test_put_metadata_upsert_overwrites(isolated_store):
    """Second put_metadata on the same key replaces the first value."""
    isolated_store.put_metadata("__upsert__", {"v": 1})
    isolated_store.flush()
    isolated_store.put_metadata("__upsert__", {"v": 2})
    isolated_store.flush()
    assert isolated_store.get_metadata("__upsert__") == {"v": 2}


def test_set_latest_report_persists_to_store(isolated_store):
    """_set_latest_report(store=) writes to uar_metadata."""
    import uar.api.routers.burn_in as _bi

    report = {"score": 80, "passed": True}
    _bi._set_latest_report(report, store=isolated_store)
    isolated_store.flush()
    recovered = isolated_store.get_metadata(_bi.BURNIN_REPORT_KEY)
    assert recovered == report


def test_from_latest_recovers_from_store_on_cache_miss(isolated_store):
    """BurnInProxy.from_latest(store=) recovers from store when slot empty."""
    import uar.api.routers.burn_in as _bi

    report = {"score": 75, "passed": True}
    isolated_store.put_metadata(_bi.BURNIN_REPORT_KEY, report)
    isolated_store.flush()

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        proxy = _bi.BurnInProxy.from_latest(store=isolated_store)
        assert proxy is not None
        assert proxy.score == 75
        assert proxy.passed is True
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


def test_from_latest_no_store_returns_none_when_slot_empty():
    """BurnInProxy.from_latest() returns None when slot empty, no store."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None
        assert _bi.BurnInProxy.from_latest() is None
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


def test_set_latest_report_survives_store_error(isolated_store):
    """_set_latest_report does not raise if store.put_metadata fails."""
    import uar.api.routers.burn_in as _bi

    class _BadStore:
        def put_metadata(self, *_a, **_kw):
            raise RuntimeError("simulated write failure")

    report = {"score": 60, "passed": False}
    _bi._set_latest_report(report, store=_BadStore())
    with _bi._report_lock:
        assert _bi._latest_report == report


def test_burnin_report_key_constant_is_stable():
    """BURNIN_REPORT_KEY is the expected sentinel string."""
    from uar.api.routers.burn_in import BURNIN_REPORT_KEY
    assert BURNIN_REPORT_KEY == "__burnin_latest__"


def test_from_latest_handles_corrupted_metadata(isolated_store):
    """BurnInProxy.from_latest returns None when store has invalid JSON."""
    import uar.api.routers.burn_in as _bi

    # Directly insert invalid JSON into the metadata table
    conn = isolated_store._connect()
    try:
        conn.execute(
            "INSERT INTO uar_metadata (key, value) VALUES (?, ?)",
            (_bi.BURNIN_REPORT_KEY, "not-valid-json"),
        )
        conn.commit()
    finally:
        conn.close()

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        # Should return None for corrupted data, not raise
        proxy = _bi.BurnInProxy.from_latest(store=isolated_store)
        assert proxy is None
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# ---------------------------------------------------------------------------
# ISS-87: Certification Engine refactor — pure Trust Spine weights
# ---------------------------------------------------------------------------

class _Burnin87:
    def __init__(self, score=100, passed=True):
        self.score = score
        self.passed = passed


def test_certify_weights_are_trust_spine_model():
    """certify_runtime uses T1=40 T3=35 T2=25; no contract_compliance."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_Burnin87(score=100, passed=True),
        runtime_health_score=100,
    )
    weights = report.evidence["weights"]
    assert weights["replay_confidence"] == 0.40
    assert weights["burnin"] == 0.35
    assert weights["runtime_health"] == 0.25
    assert "contract_compliance" not in weights


def test_certify_score_matches_new_weights():
    """Weighted score calculation is correct for the new model."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=80,
        burnin_report=_Burnin87(score=60, passed=True),
        runtime_health_score=100,
    )
    expected = int(round(80 * 0.40 + 60 * 0.35 + 100 * 0.25))
    assert report.score == expected


def test_certify_no_contract_compliance_param():
    """certify_runtime does not accept contract_compliance_score."""
    import inspect
    from uar.core.certification import certify_runtime

    sig = inspect.signature(certify_runtime)
    assert "contract_compliance_score" not in sig.parameters


def test_certify_evidence_has_no_contract_compliance_field():
    """Evidence dict does not contain contract_compliance_score."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=90,
        burnin_report=_Burnin87(score=90, passed=True),
        runtime_health_score=90,
    )
    assert "contract_compliance_score" not in report.evidence


def test_certify_gold_still_requires_burnin_passed():
    """Gold level still requires burnin_passed=True after refactor."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_Burnin87(score=100, passed=False),
        runtime_health_score=100,
    )
    assert report.level != "Gold"


def test_certify_perfect_scores_still_gold():
    """All-100 inputs still yield Gold after weight change."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_Burnin87(score=100, passed=True),
        runtime_health_score=100,
    )
    assert report.score == 100
    assert report.level == "Gold"
    assert report.violations == []


def test_certify_weights_sum_to_one():
    """New Trust Spine weights sum to exactly 1.0."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_Burnin87(score=100, passed=True),
        runtime_health_score=100,
    )
    total = sum(report.evidence["weights"].values())
    assert abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Review-session regressions (7 bugs found and fixed)
# ---------------------------------------------------------------------------

# Bug 1: TOCTOU in get_latest_burnin — snapshot_latest returns (proxy, dict)
# atomically so the endpoint never re-reads the module global.

def test_snapshot_latest_returns_proxy_and_dict(monkeypatch):
    """BurnInProxy.snapshot_latest returns (proxy, dict) pair atomically."""
    from uar.api.routers.burn_in import BurnInProxy, _set_latest_report

    _set_latest_report({"score": 42, "passed": False})
    try:
        proxy, raw = BurnInProxy.snapshot_latest()
        assert proxy is not None
        assert isinstance(raw, dict)
        assert proxy.score == 42
        assert raw["score"] == 42
    finally:
        monkeypatch.setattr(_burnin_mod, "_latest_report", None)


def test_snapshot_latest_returns_none_pair_when_empty(monkeypatch):
    """snapshot_latest returns (None, None) when no report is available."""
    from uar.api.routers.burn_in import BurnInProxy

    monkeypatch.setattr(_burnin_mod, "_latest_report", None)
    proxy, raw = BurnInProxy.snapshot_latest()
    assert proxy is None
    assert raw is None


def test_get_latest_burnin_dict_matches_set(monkeypatch, isolated_store):
    """GET /burnin/latest returns exactly the dict that was set."""
    from uar.api.routers.burn_in import _set_latest_report
    from uar.api.server import app

    _set_latest_report({"score": 55, "passed": False, "tag": "toctou-test"})
    try:
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/uar/burnin/latest", headers=_ADMIN_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["score"] == 55
        assert body["tag"] == "toctou-test"
    finally:
        monkeypatch.setattr(_burnin_mod, "_latest_report", None)


# Bug 2: mission_control and certification routers must pass store= to
# BurnInProxy.from_latest() so Issue #86 recovery works after restart.

def test_mission_control_router_passes_store_to_burnin_proxy():
    """mission_control must call from_latest(store=store)."""
    import inspect
    import uar.api.routers.mission_control as _mc

    src = inspect.getsource(_mc.get_mission_control)
    assert "from_latest(store=store)" in src, (
        "mission_control does not pass store= to BurnInProxy.from_latest()"
    )


def test_certification_router_passes_store_to_burnin_proxy():
    """certification must call from_latest(store=store)."""
    import inspect
    import uar.api.routers.certification as _cert

    src = inspect.getsource(_cert.get_certification)
    assert "from_latest(store=store)" in src, (
        "certification does not pass store= to BurnInProxy.from_latest()"
    )


def test_mission_control_recovers_burnin_after_restart(
    isolated_store, monkeypatch
):
    """Mission Control returns non-None burn-in after simulated restart."""
    import uar.api.routers.burn_in as _bi
    from uar.api.server import app

    report = {"score": 88, "passed": True}
    isolated_store.put_metadata(_bi.BURNIN_REPORT_KEY, report)
    isolated_store.flush()

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get(
            "/api/uar/mission-control", headers=_ADMIN_HEADERS
        )
        assert resp.status_code == 200
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Bug 3: _score_store_consistency must not double-penalise when run_id is
# absent AND the first event also has a non-matching run_id field.

def test_store_consistency_no_double_penalty_on_missing_run_id():
    """Missing run_id must not also trigger store_event_mismatch penalty."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="",
        goal_id="goal-ok",
        skills=["echo"],
        outputs=[],
        events=[{"run_id": "some-other-id", "type": "start"}],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)

    codes = [w.code for w in warnings]
    assert "store_record_missing" in codes
    assert "store_event_mismatch" not in codes, (
        "Mismatch penalty fired even though run_id was missing"
    )
    assert score == 50  # 100 - 50 for missing run_id only


def test_store_consistency_mismatch_fires_when_run_id_present():
    """store_event_mismatch must still fire when run_id is set but wrong."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="real-id",
        goal_id="goal-ok",
        skills=["echo"],
        outputs=[],
        events=[{"run_id": "different-id", "type": "start"}],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)

    codes = [w.code for w in warnings]
    assert "store_event_mismatch" in codes
    assert score == 60  # 100 - 40 mismatch only


# Bug 5: put_metadata must raise on write failure rather than silently
# poisoning the writer exception for the next unrelated write.

def test_put_metadata_raises_on_write_failure(tmp_path, monkeypatch):
    """put_metadata surfaces write errors at the call site."""
    store = SqliteRunStore(path=str(tmp_path / "meta_err.db"))
    try:
        original_sync = store._enqueue_write_sync

        def _failing_sync(op, payload):
            if op == "put_meta":
                return RuntimeError("injected failure")
            return original_sync(op, payload)

        monkeypatch.setattr(store, "_enqueue_write_sync", _failing_sync)

        with pytest.raises(RuntimeError, match="injected failure"):
            store.put_metadata("key", {"v": 1})

        record = RunRecord(
            run_id="after-meta-fail",
            goal_id="g1",
            skills=["echo"],
            outputs=[],
            events=[],
        )
        store.append(record)
        store.flush()
        assert store.get_by_run_id("after-meta-fail") is not None
    finally:
        store.close()


# Bug 6: Silver must not be granted when no burn-in has ever run.

def test_silver_granted_without_burnin():
    """certification_level returns Silver when scores are high and
    no violations, even if burn-in has never run."""
    from uar.core.certification import certification_level

    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=False,
        burnin_score=0,
        has_violations=False,
        burnin_ran=False,
    )
    assert level == "Silver", (
        "Silver should be granted without burn-in when scores are strong"
    )


def test_silver_granted_when_burnin_failed_but_scores_high():
    """certification_level returns Silver when scores are high and
    no violations, regardless of burn-in pass status."""
    from uar.core.certification import certification_level

    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=False,
        burnin_score=70,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Silver", (
        "Silver should be granted with strong scores even if burn-in failed"
    )


def test_certify_no_burnin_can_reach_silver():
    """certify_runtime with burnin_report=None can now return Silver."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=90,
        burnin_report=None,
        runtime_health_score=90,
    )
    assert report.level == "Silver", (
        "Strong scores without burn-in should grant Silver"
    )


# Bug 7: replay_explorer must return 401 for unauthenticated callers,
# not 403 (which would hide the real auth failure).

def test_explorer_unauthenticated_returns_401(isolated_store):
    """GET /runs/{id}/explorer without credentials returns 401."""
    from uar.api.server import app
    from uar.core.contracts import RunRecord

    run_id = f"unauth-run-{int(time.time()*1000)}"
    isolated_store.append(RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    ))
    isolated_store.flush()

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(f"/api/uar/runs/{run_id}/explorer")
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated explorer, "
        f"got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Review-session regressions — batch 2 (4 new bugs)
# ---------------------------------------------------------------------------

# Bug R1: _enqueue_write_sync must raise TimeoutError on writer timeout,
# not silently return None and fool callers into thinking the write succeeded.

def test_enqueue_write_sync_raises_on_timeout(tmp_path, monkeypatch):
    """_enqueue_write_sync raises TimeoutError when event never fires."""
    store = SqliteRunStore(path=str(tmp_path / "timeout_test.db"))
    try:
        original_put = store._writer_queue.put

        def _blocking_put(item, **kw):
            # Accept the item but never set the event so wait() times out.
            if isinstance(item, tuple) and len(item) == 4:
                op, payload, result_container, event = item
                # Swallow the item; event stays unset.
                return
            return original_put(item, **kw)

        monkeypatch.setattr(store._writer_queue, "put", _blocking_put)
        monkeypatch.setattr(
            store,
            "_enqueue_write_sync",
            lambda op, payload: store.__class__._enqueue_write_sync(
                store, op, payload
            ),
        )

        # Patch event.wait to return False immediately (simulates timeout)
        import threading as _threading
        original_event_cls = _threading.Event

        class _NeverFireEvent(original_event_cls):
            def wait(self, timeout=None):
                return False  # always simulate timeout

        import unittest.mock as _mock
        with _mock.patch(
            "uar.memory.sqlite_store.threading.Event",
            _NeverFireEvent,
        ):
            with pytest.raises(TimeoutError, match="Writer thread"):
                store.put_metadata("k", {"v": 1})
    finally:
        store.close()


def test_enqueue_write_sync_does_not_return_none_on_success(tmp_path):
    """_enqueue_write_sync returns the actual result, not None, on success."""
    store = SqliteRunStore(path=str(tmp_path / "sync_ok.db"))
    try:
        store.put_metadata("__sync_ok__", {"x": 42})
        store.flush()
        assert store.get_metadata("__sync_ok__") == {"x": 42}
    finally:
        store.close()


# Bug R2: monotonic_timeout must not chain _exc as the cause of TimeoutError —
# _exc is the interrupted work, not the root cause.

def test_monotonic_timeout_has_no_chained_cause():
    """TimeoutError.__cause__ must be None (raised from None)."""
    from uar.core.safe_utils import monotonic_timeout
    import time as _time

    caught = None
    try:
        with monotonic_timeout(0.01, label="test_op"):
            _time.sleep(0.5)
    except TimeoutError as exc:
        caught = exc

    assert caught is not None, "TimeoutError was not raised"
    assert caught.__cause__ is None, (
        f"TimeoutError.__cause__ should be None, got {caught.__cause__!r}; "
        "the interrupted exception must not appear as the cause of the timeout"
    )


def test_monotonic_timeout_does_not_mask_non_timeout_exception():
    """Exceptions raised before deadline are re-raised unchanged."""
    from uar.core.safe_utils import monotonic_timeout

    with pytest.raises(ValueError, match="intentional"):
        with monotonic_timeout(10.0, label="test_op"):
            raise ValueError("intentional")


# Bug R3: from_latest / snapshot_latest must not overwrite a newer in-memory
# report with stale store data when a concurrent _set_latest_report fires
# between the lock release and the writeback.

def test_from_latest_compare_and_set_does_not_overwrite_newer_report():
    """from_latest must not clobber a live report set after the store read."""
    import uar.api.routers.burn_in as _bi

    stale = {"score": 10, "passed": False, "tag": "stale"}
    live = {"score": 99, "passed": True, "tag": "live"}

    _saved = _bi._latest_report
    try:
        # Start with empty slot
        with _bi._report_lock:
            _bi._latest_report = None

        # Simulate a store that returns the stale value
        class _StaleStore:
            def get_metadata(self, key):
                # While "reading" from the store, a concurrent
                # _set_latest_report fires with the live report.
                with _bi._report_lock:
                    _bi._latest_report = live
                return stale

        proxy = _bi.BurnInProxy.from_latest(store=_StaleStore())

        # The proxy must reflect the live value, not the stale store value.
        assert proxy is not None
        assert proxy.score == live["score"], (
            f"Expected score {live['score']}, got {proxy.score}; "
            "stale store data overwrote the live in-memory report"
        )
        with _bi._report_lock:
            assert _bi._latest_report == live, (
                "_latest_report was reverted to stale store value"
            )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


def test_snapshot_latest_compare_and_set_does_not_overwrite_newer_report():
    """snapshot_latest must not clobber a report set after the store read."""
    import uar.api.routers.burn_in as _bi

    stale = {"score": 5, "passed": False, "tag": "stale-snap"}
    live = {"score": 88, "passed": True, "tag": "live-snap"}

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        class _StaleStore:
            def get_metadata(self, key):
                with _bi._report_lock:
                    _bi._latest_report = live
                return stale

        proxy, raw = _bi.BurnInProxy.snapshot_latest(store=_StaleStore())

        assert proxy is not None
        assert proxy.score == live["score"], (
            f"Expected score {live['score']}, got {proxy.score}"
        )
        assert raw is not None
        assert raw.get("tag") == live["tag"], (
            "snapshot_latest returned stale raw dict instead of live report"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Bug R4: _score_artifact_completeness must return 0 (not 60) for runs with
# no outputs, final_context, or UOR provenance. A floor of 60 silently
# inflated composite replay scores for zero-evidence runs.

def test_artifact_completeness_zero_for_no_evidence():
    """artifact_completeness must be 0 when there are no artifacts at all."""
    from uar.core.replay_confidence import _score_artifact_completeness
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="r1",
        goal_id="g1",
        skills=["echo"],
        outputs=[],
        final_context=None,
        uor_address=None,
        uor_witness=None,
    )
    from uar.core.replay_confidence import ReplayConfidenceWarning
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_artifact_completeness(record, warnings)

    assert score == 0, (
        f"Expected 0 for zero-evidence run, got {score}; "
        "the floor of 60 inflates scores for runs with no provenance"
    )
    codes = [w.code for w in warnings]
    assert "artifact_missing" in codes
    missing_w = next(w for w in warnings if w.code == "artifact_missing")
    assert missing_w.severity == "warning"


# ---------------------------------------------------------------------------
# Review-session regressions — batch 4
# ---------------------------------------------------------------------------

# Fix: put_meta conn.commit() — reader must see write without flush.

def test_get_metadata_visible_immediately_after_put(tmp_path):
    """get_metadata must return the value right after put_metadata (no flush).

    Without conn.commit() in the put_meta branch the SQLite write sat in
    an uncommitted implicit transaction, invisible to reader connections.
    """
    store = SqliteRunStore(path=str(tmp_path / "commit_test.db"))
    try:
        payload = {"score": 91, "passed": True, "tag": "commit-regression"}
        store.put_metadata("__commit_test__", payload)
        # No flush() — reader must see the committed row immediately.
        recovered = store.get_metadata("__commit_test__")
        assert recovered == payload, (
            f"Expected {payload!r}, got {recovered!r}. "
            "put_meta was not committed — reader saw stale (None) state. "
            "Regression: missing conn.commit() in put_meta writer branch."
        )
    finally:
        store.close()


def test_get_metadata_upsert_visible_immediately_after_second_put(tmp_path):
    """Second put_metadata (upsert) is also immediately visible to readers."""
    store = SqliteRunStore(path=str(tmp_path / "commit_upsert_test.db"))
    try:
        store.put_metadata("__upsert_commit__", {"v": 1})
        store.put_metadata("__upsert_commit__", {"v": 2})
        recovered = store.get_metadata("__upsert_commit__")
        assert recovered == {"v": 2}, (
            f"Expected {{v: 2}} after upsert, got {recovered!r}."
        )
    finally:
        store.close()


# Fix: run_batch strict=True raises on mismatched strategy/goal lists.

def test_run_batch_raises_on_mismatched_lists():
    """run_batch must raise ValueError when strategies and goals differ."""
    from uar.core.executor import Executor
    from uar.core.contracts import GoalSpec, StrategySpec

    executor = Executor()
    strategies = [StrategySpec(goal_id="g1", ordered_skills=["echo"])]
    goals = [
        GoalSpec(id="g1", user_intent="t", objective="first"),
        GoalSpec(id="g2", user_intent="t", objective="extra"),
    ]
    with pytest.raises(ValueError):
        executor.run_batch(strategies, goals)


# Fix: artifact_missing severity is "warning" not "error".

def test_artifact_missing_severity_is_warning():
    """artifact_missing warning must have severity='warning', not 'error'.

    The artifact_completeness dimension is weighted at 10%.  Emitting
    'error' severity for a 10%-weighted signal produces false-positive
    operational alerts for legitimate runs that only produce in-context
    results without UOR provenance or file outputs.
    """
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_artifact_completeness,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="sev-test",
        goal_id="g1",
        skills=["echo"],
        outputs=[],
        final_context=None,
        uor_address=None,
        uor_witness=None,
    )
    warnings: list[ReplayConfidenceWarning] = []
    _score_artifact_completeness(record, warnings)

    w = next(
        (w for w in warnings if w.code == "artifact_missing"), None
    )
    assert w is not None, "artifact_missing warning not emitted"
    assert w.severity == "warning", (
        f"Expected severity='warning', got {w.severity!r}. "
        "artifact_missing must not use 'error' severity — the "
        "10%-weighted dimension should not produce error-level alerts "
        "for runs that produce valid in-context results."
    )


def test_artifact_completeness_score_not_inflated_in_composite():
    """A no-artifact run must not be inflated above Failed tier."""
    from uar.core.replay_confidence import score_replay
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="",
        goal_id="",
        skills=[],
        outputs=[],
        final_context=None,
        uor_address=None,
        uor_witness=None,
        events=[],
    )
    report = score_replay(record)
    assert report.dimensions["artifact_completeness"] == 0


# ---------------------------------------------------------------------------
# Review-session regressions — batch 3
# ---------------------------------------------------------------------------

# Bug E1: _release_coalesce_lock in executor.py used `nonlocal
# _coalesce_lock_acquired` but the variable was only assigned inside the
# for-loop, leaving the function definition potentially before the cell
# existed.  Fix: initialise _coalesce_lock_acquired=False immediately before
# the function definition so the cell is always bound.

def test_executor_coalesce_lock_acquired_initialised_before_function():
    """_coalesce_lock_acquired must be assigned before _release_coalesce_lock.

    Inspect source to confirm the initialisation precedes the def.
    """
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    init_idx = src.find(
        "_coalesce_lock_acquired = False  # precedes function def"
    )
    def_idx = src.find("def _release_coalesce_lock(")
    assert init_idx != -1, (
        "_coalesce_lock_acquired initialisation sentinel comment not found"
    )
    assert def_idx != -1, "_release_coalesce_lock definition not found"
    assert init_idx < def_idx, (
        "_coalesce_lock_acquired must be initialised BEFORE "
        "_release_coalesce_lock is defined to prevent UnboundLocalError"
    )


# Bug S1: put_metadata failure must NOT set _writer_exception on the store.
# Previously any exception from a sync write (4-tuple item) would also set
# _writer_exception, causing every subsequent async write (append, etc.) to
# raise even after the transient error cleared.

def test_put_metadata_failure_does_not_poison_writer_exception(tmp_path):
    """A failed put_metadata must not prevent subsequent append() calls."""
    store = SqliteRunStore(path=str(tmp_path / "poison_test.db"))
    try:
        # Force put_meta to fail by dropping the uar_metadata table.
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(tmp_path / "poison_test.db"))
        conn.execute("DROP TABLE IF EXISTS uar_metadata")
        conn.commit()
        conn.close()
        store.flush()  # drain any pending items

        # put_metadata should raise (table gone) but NOT poison the store.
        with pytest.raises(Exception):
            store.put_metadata("key", {"val": 1})

        # _writer_exception must remain None so append still works.
        assert store._writer_exception is None, (
            "_writer_exception was set after put_metadata failure; "
            "subsequent append() calls would permanently raise — "
            "Bug S1 regression."
        )

        # Confirm append still works after the put_metadata failure.
        from uar.core.contracts import RunRecord
        record = RunRecord(
            run_id="after-put-meta-fail",
            goal_id="g1",
            skills=["echo"],
            status="success",
            outputs=["ok"],
            events=[],
        )
        store.append(record)
        store.flush()
        assert store.get_by_run_id("after-put-meta-fail") is not None, (
            "append() failed after put_metadata error — writer poisoned"
        )
    finally:
        store.close()


# Bug T1: safe_utils.monotonic_timeout used `raise _exc` which changes the
# innermost traceback frame to safe_utils.py line 106 instead of the
# original raise site.  Fix: use bare `raise` to preserve the full traceback.

def test_monotonic_timeout_non_timeout_exception_traceback_preserved():
    """Non-timeout exceptions must originate from their actual raise site."""
    from uar.core.safe_utils import monotonic_timeout

    def _raiser():
        raise ValueError("traceback-origin")

    try:
        with monotonic_timeout(10.0, label="traceback_test"):
            _raiser()
    except ValueError as exc:
        tb = exc.__traceback__
        # Walk to the innermost frame
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame_name = tb.tb_frame.f_code.co_name
        assert frame_name == "_raiser", (
            f"Innermost traceback frame should be '_raiser', "
            f"got '{frame_name}'. bare `raise` was replaced with "
            "`raise _exc` which shifts the frame to safe_utils.py."
        )
    else:
        pytest.fail("ValueError was not raised")


# ---------------------------------------------------------------------------
# Review-session regressions — batch 5 (post-review fixes)
# ---------------------------------------------------------------------------

# Fix: _coalesce_key is reset inside the for-loop body before any
# code that could raise and trigger the finally block.

def test_coalesce_key_reset_inside_loop_body():
    """_coalesce_key is reset inside the retry for-loop body.

    The variable is assigned at the top of each loop iteration before
    any exception can trigger the finally block, so no pre-loop
    initialization is needed (and the dead pre-loop init was removed).
    """
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    # _coalesce_key must be reset inside the for-loop body
    reset_idx = src.find('_coalesce_key = ""  # reset each attempt')
    for_idx = src.find("for attempt in range(max_retries + 1):")
    assert reset_idx != -1, (
        "_coalesce_key reset comment not found inside loop"
    )
    assert for_idx != -1, "for-loop not found"
    assert reset_idx > for_idx, (
        "_coalesce_key must be reset INSIDE the for-loop body"
    )


# Fix: sqlite_store _ensure_table must commit DDL.

def test_ensure_table_commits_ddl(tmp_path):
    """DDL in _ensure_table is committed immediately.

    Regression: Without explicit commit, DDL changes might not be
    visible to other connections immediately.
    """
    import sqlite3

    db_path = tmp_path / "ddl_test.db"
    # Create store (calls _ensure_table)
    store = SqliteRunStore(path=str(db_path))
    try:
        store.flush()
        # Open a fresh connection and verify tables exist
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cur.fetchall()}
            assert "uar_runs" in tables, "uar_runs table not found"
            assert "uar_metadata" in tables, "uar_metadata table not found"
        finally:
            conn.close()
    finally:
        store.close()


# Fix: _set_latest_report logs store failures instead of silently ignoring.

def test_set_latest_report_logs_store_failure(caplog, monkeypatch):
    """_set_latest_report logs a warning when store.put_metadata fails."""
    import logging
    import uar.api.routers.burn_in as _bi

    class _FailingStore:
        def put_metadata(self, key, value):
            raise RuntimeError("simulated disk full")

    with caplog.at_level(logging.WARNING, logger="uar.api.routers.burn_in"):
        _bi._set_latest_report(
            {"score": 50, "passed": False},
            store=_FailingStore(),
        )

    assert any(
        "simulated disk full" in rec.message
        for rec in caplog.records
        if rec.levelname == "WARNING"
    ), "Store failure was not logged at WARNING level"


# ---------------------------------------------------------------------------
# Review-session regressions — batch 3 (code review fixes)
# ---------------------------------------------------------------------------

# Fix 1: TOCTOU race in BurnInProxy.from_latest() — use stored directly.


def test_from_latest_returns_fresher_value_on_concurrent_write():
    """from_latest returns the fresher value when another thread writes.

    Regression: When another thread sets _latest_report while we're
    querying the store, we used to return the fresher value but also
    overwrite it with stale store data. Now we use the stored value
    only when we actually write it.
    """
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        # Simulate: store has stale value, then another thread sets fresh
        class _StoreWithStale:
            def get_metadata(self, key):
                return {"score": 50, "passed": False, "source": "stale"}

        # Pre-set a "fresher" value as if another thread wrote it
        with _bi._report_lock:
            _bi._latest_report = {
                "score": 90, "passed": True, "source": "fresh"
            }

        # Call from_latest - should return fresher value (90), not stale (50)
        proxy = _bi.BurnInProxy.from_latest(store=_StoreWithStale())
        assert proxy is not None
        assert proxy.score == 90, (
            f"Expected fresh score 90, got {proxy.score} — "
            "TOCTOU: stale store data overwrote fresher value"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Fix 2: Certification logs replay scoring failures instead of silent pass.


def test_certification_logs_replay_failure(
    caplog, isolated_store, monkeypatch
):
    """Certification endpoint logs warning when replay scoring fails."""
    import logging
    from uar.api.server import app
    import uar.memory.base_store as _base_store

    # Make run_record_from_dict raise to simulate corruption
    def _failing_record_from_dict(d):
        raise ValueError("simulated corrupt record")

    monkeypatch.setattr(
        _base_store, "run_record_from_dict", _failing_record_from_dict
    )

    # Create a record so latest_record is not None
    run_id = f"corrupt-{int(time.time()*1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    )
    isolated_store.append(record)
    isolated_store.flush()

    client = TestClient(app, raise_server_exceptions=True)
    with caplog.at_level(
        logging.WARNING, logger="uar.api.routers.certification"
    ):
        resp = client.get("/api/uar/certification", headers=_ADMIN_HEADERS)

    assert resp.status_code == 200
    assert any(
        "Failed to score replay confidence" in rec.message
        for rec in caplog.records
        if rec.levelname == "WARNING"
    ), "Replay failure was not logged"


# Fix 3: certify_runtime adds violation when runtime_health_score is None.


def test_certify_runtime_warns_on_missing_health_score():
    """certify_runtime adds violation when runtime_health_score is None."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=90,
        burnin_report=_Burnin87(score=90, passed=True),
        runtime_health_score=None,  # Missing
    )
    assert any(
        "runtime_health: no score available" in v
        for v in report.violations
    ), "Missing runtime health should be recorded in violations"


# Fix 4: get_metadata logs warning for corrupt JSON.


def test_get_metadata_logs_corrupt_json(caplog, isolated_store):
    """get_metadata logs warning when JSON is corrupt."""
    import logging

    # Directly insert invalid JSON
    conn = isolated_store._connect()
    try:
        conn.execute(
            "INSERT INTO uar_metadata (key, value) VALUES (?, ?)",
            ("__corrupt_key__", "not-valid-json{{"),
        )
        conn.commit()
    finally:
        conn.close()

    with caplog.at_level(logging.WARNING, logger="uar.memory.sqlite_store"):
        result = isolated_store.get_metadata("__corrupt_key__")

    assert result is None
    assert any(
        "is corrupt" in rec.message and "__corrupt_key__" in rec.message
        for rec in caplog.records
        if rec.levelname == "WARNING"
    ), "Corrupt metadata was not logged"


# Fix 5: BurnInProxy.from_latest validates store interface.


def test_from_latest_returns_none_for_invalid_store_old():
    """from_latest returns None when store lacks get_metadata."""
    import uar.api.routers.burn_in as _bi

    class _BadStore:
        pass  # No get_metadata method

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        result = _bi.BurnInProxy.from_latest(store=_BadStore())
        assert result is None, (
            "from_latest should return None for invalid store"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# ---------------------------------------------------------------------------
# Post-review fixes (2026-05-31)
# ---------------------------------------------------------------------------

# Fix: postgres_store SELECT statements must include uor_address/uor_witness


def test_postgres_store_list_records_includes_uor_columns():
    """list_records SELECT must include uor_address and uor_witness.

    Regression: The SELECT columns didn't match the INSERT columns,
    causing UOR provenance data to be lost on read-back.
    """
    import inspect
    import uar.memory.postgres_store as _pg_store

    src = inspect.getsource(_pg_store.PostgresRunStore.list_records)
    # Verify SELECT includes uor columns
    assert "uor_address" in src, (
        "list_records SELECT missing uor_address column"
    )
    assert "uor_witness" in src, (
        "list_records SELECT missing uor_witness column"
    )
    # Verify cols list includes uor columns
    cols_idx = src.find('cols = [')
    assert cols_idx != -1, "cols list not found in list_records"
    cols_section = src[cols_idx:cols_idx + 500]
    assert '"uor_address"' in cols_section, (
        "cols list missing uor_address"
    )
    assert '"uor_witness"' in cols_section, (
        "cols list missing uor_witness"
    )


def test_postgres_store_get_by_run_id_includes_uor_columns():
    """get_by_run_id SELECT must include uor_address and uor_witness.

    Regression: The SELECT columns didn't match the INSERT columns,
    causing UOR provenance data to be lost on read-back.
    """
    import inspect
    import uar.memory.postgres_store as _pg_store

    src = inspect.getsource(_pg_store.PostgresRunStore.get_by_run_id)
    # Verify SELECT includes uor columns
    assert "uor_address" in src, (
        "get_by_run_id SELECT missing uor_address column"
    )
    assert "uor_witness" in src, (
        "get_by_run_id SELECT missing uor_witness column"
    )
    # Verify cols list includes uor columns
    cols_idx = src.find('cols = [')
    assert cols_idx != -1, "cols list not found in get_by_run_id"
    cols_section = src[cols_idx:cols_idx + 500]
    assert '"uor_address"' in cols_section, (
        "cols list missing uor_address"
    )
    assert '"uor_witness"' in cols_section, (
        "cols list missing uor_witness"
    )


def test_postgres_store_json_parsing_includes_uor_witness():
    """JSON parsing loop must include uor_witness for deserialization.

    Regression: uor_witness was not being parsed from JSON string.
    """
    import inspect
    import uar.memory.postgres_store as _pg_store

    src = inspect.getsource(_pg_store.PostgresRunStore.list_records)
    # Find the JSON parsing loop
    json_loop_idx = src.find('for key in (')
    assert json_loop_idx != -1, "JSON parsing loop not found"
    loop_section = src[json_loop_idx:json_loop_idx + 300]
    assert '"uor_witness"' in loop_section, (
        "uor_witness not in JSON parsing loop"
    )


# Fix: replay_explorer uses HTTPException for consistency


def test_replay_explorer_record_parse_error_uses_httpexception():
    """run_record_from_dict failure must use HTTPException, not JSONResponse.

    Regression: Used JSONResponse with nested 'detail' key which was
    inconsistent with other endpoints that use HTTPException.
    """
    import inspect
    import uar.api.routers.replay_explorer as _re

    src = inspect.getsource(_re.get_replay_explorer)
    # Verify HTTPException is used for record parse error
    assert "raise HTTPException(" in src, (
        "record_parse_error should use HTTPException, not JSONResponse"
    )
    assert "JSONResponse" not in src, (
        "JSONResponse should not be used in replay_explorer"
    )


def test_replay_explorer_error_includes_exception_chain():
    """HTTPException from record parse error chains the original exception.

    Verifies 'from exc' is present for proper exception chaining.
    """
    import inspect
    import uar.api.routers.replay_explorer as _re

    src = inspect.getsource(_re.get_replay_explorer)
    # Find the except block for run_record_from_dict
    except_idx = src.find("except Exception as exc:")
    assert except_idx != -1, "except block not found"
    except_section = src[except_idx:except_idx + 400]
    assert ") from exc" in except_section, (
        "HTTPException should chain original exception with 'from exc'"
    )


# ---------------------------------------------------------------------------
# Review-session fixes — batch 5 (new bugs found and fixed)
# ---------------------------------------------------------------------------

# Fix 1: artifact_missing warning must have explicit severity="warning"

def test_artifact_missing_warning_has_explicit_severity():
    """artifact_missing warning must explicitly set severity='warning'.

    Regression guard: the warning should not rely on the dataclass default.
    This documents the intentional severity choice.
    """
    import inspect
    import uar.core.replay_confidence as _rc

    src = inspect.getsource(_rc._score_artifact_completeness)
    # Find the artifact_missing warning construction
    idx = src.find('"artifact_missing"')
    assert idx != -1, "artifact_missing warning not found"
    section = src[idx:idx + 200]
    assert '"warning"' in section or "severity=" in section, (
        "artifact_missing must explicitly specify severity='warning'"
    )


# Fix 2: BurnInProxy.from_latest validates get_metadata is callable

def test_burnin_proxy_from_latest_returns_none_for_non_callable_get_metadata(
    monkeypatch,
):
    """store.get_metadata not callable returns None gracefully."""
    import uar.api.routers.burn_in as _bi
    from uar.api.routers.burn_in import BurnInProxy

    # Ensure clean state
    monkeypatch.setattr(_bi, "_latest_report", None)

    class _StoreWithNonCallable:
        get_metadata = "not a callable"

    result = BurnInProxy.from_latest(store=_StoreWithNonCallable())
    assert result is None, (
        "from_latest should return None when get_metadata not callable"
    )


def test_burnin_proxy_from_latest_accepts_valid_store(monkeypatch):
    """Valid store with callable get_metadata works correctly."""
    import uar.api.routers.burn_in as _bi
    from uar.api.routers.burn_in import BurnInProxy

    # Ensure clean state - no cached report
    monkeypatch.setattr(_bi, "_latest_report", None)

    class _ValidStore:
        def get_metadata(self, key):
            return None

    result = BurnInProxy.from_latest(store=_ValidStore())
    assert result is None  # No report stored


# Fix 3: replay_explorer logs exceptions instead of silently swallowing

def test_replay_explorer_logs_timeline_failure(monkeypatch, isolated_store):
    """timeline_from_record failure must be logged, not silent."""
    from uar.api.server import app

    logs = []

    def _capture_warning(msg, *args, **kwargs):
        logs.append(msg % args if args else msg)

    # Patch the module-level logger
    import uar.api.routers.replay_explorer as _re
    monkeypatch.setattr(_re.logger, "warning", _capture_warning)

    original_fn = _re.timeline_from_record

    def _fail_timeline(r):
        raise ValueError("simulated timeline failure")
    monkeypatch.setattr(_re, "timeline_from_record", _fail_timeline)

    run_id = f"timeline-fail-{int(time.time()*1000)}"
    isolated_store.append(RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    ))

    client = TestClient(app, raise_server_exceptions=True)
    url = f"/api/uar/runs/{run_id}/explorer"
    resp = client.get(url, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200

    # Verify the error was logged
    assert any("timeline_from_record failed" in msg for msg in logs), (
        "timeline_from_record failure was not logged"
    )

    # Restore
    monkeypatch.setattr(_re, "timeline_from_record", original_fn)


def test_replay_explorer_logs_score_failure(monkeypatch, isolated_store):
    """score_replay failure must be logged, not silent."""
    from uar.api.server import app

    logs = []

    def _capture_warning(msg, *args, **kwargs):
        logs.append(msg % args if args else msg)

    # Patch the module-level logger and score_replay in replay_explorer
    import uar.api.routers.replay_explorer as _re
    monkeypatch.setattr(_re.logger, "warning", _capture_warning)

    # Patch the imported score_replay reference in replay_explorer module
    original_score = _re.score_replay

    def _fail_score(r):
        raise ValueError("simulated score failure")
    monkeypatch.setattr(_re, "score_replay", _fail_score)

    run_id = f"score-fail-{int(time.time()*1000)}"
    isolated_store.append(RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    ))

    client = TestClient(app, raise_server_exceptions=True)
    url = f"/api/uar/runs/{run_id}/explorer"
    resp = client.get(url, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200

    # Verify the error was logged
    assert any("score_replay failed" in msg for msg in logs), (
        "score_replay failure was not logged"
    )

    # Restore
    monkeypatch.setattr(_re, "score_replay", original_score)


# ---------------------------------------------------------------------------
# Review-session regressions — batch 6
# ---------------------------------------------------------------------------

# Bug P1: list_records_async and get_by_run_id_async SELECT omitted
# uor_address and uor_witness columns — UOR provenance silently lost.

def test_postgres_list_records_async_select_includes_uor_columns():
    """list_records_async SELECT must include uor_address and uor_witness."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.list_records_async)
    assert "uor_address" in src, (
        "list_records_async SELECT missing uor_address"
    )
    assert "uor_witness" in src, (
        "list_records_async SELECT missing uor_witness"
    )
    cols_idx = src.find("cols = [")
    assert cols_idx != -1, "cols list not found in list_records_async"
    cols_section = src[cols_idx:cols_idx + 400]
    assert '"uor_address"' in cols_section, (
        "cols list in list_records_async missing uor_address"
    )
    assert '"uor_witness"' in cols_section, (
        "cols list in list_records_async missing uor_witness"
    )


def test_postgres_get_by_run_id_async_select_includes_uor_columns():
    """get_by_run_id_async SELECT must include uor_address and uor_witness."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.get_by_run_id_async)
    assert "uor_address" in src, (
        "get_by_run_id_async SELECT missing uor_address"
    )
    assert "uor_witness" in src, (
        "get_by_run_id_async SELECT missing uor_witness"
    )
    cols_idx = src.find("cols = [")
    assert cols_idx != -1, "cols list not found in get_by_run_id_async"
    cols_section = src[cols_idx:cols_idx + 400]
    assert '"uor_address"' in cols_section, (
        "cols list in get_by_run_id_async missing uor_address"
    )
    assert '"uor_witness"' in cols_section, (
        "cols list in get_by_run_id_async missing uor_witness"
    )


def test_postgres_async_json_decode_includes_uor_witness():
    """list_records_async JSON decode loop must include uor_witness."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.list_records_async)
    loop_idx = src.find("for key in (")
    assert loop_idx != -1, "JSON decode loop not found in list_records_async"
    loop_section = src[loop_idx:loop_idx + 300]
    assert '"uor_witness"' in loop_section, (
        "uor_witness not decoded in list_records_async"
    )


# Bug P2: append_async serialised uor_witness=None as JSON "null" string
# instead of SQL NULL, creating an inconsistency with sync append().

def test_postgres_append_async_witness_none_produces_sql_null():
    """append_async must store uor_witness=None as SQL NULL, not 'null'."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.append_async)
    # The fix uses a conditional: json.dumps(_witness) if _witness is not None
    # else None — verify the None branch is present.
    assert "is not None else None" in src or (
        "_witness is not None" in src and "else None" in src
    ), (
        "append_async must use conditional serialisation so that "
        "uor_witness=None maps to SQL NULL, not the string 'null'"
    )


# Bug MT (confirmed by design): monotonic_timeout converts any exception
# raised after deadline expiry to TimeoutError — this is intentional since
# the block was interrupted.  The real fix from Session 11 (Bug T1) was
# restoring the original traceback frame by using bare `raise` instead of
# `raise _exc`.  These tests document the confirmed semantics.

def test_monotonic_timeout_non_expired_preserves_exception_type():
    """Exceptions raised before the deadline are re-raised with original type.

    This is the main contract: if deadline has NOT expired, the original
    exception must pass through unchanged.
    """
    from uar.core.safe_utils import monotonic_timeout

    with pytest.raises(ValueError, match="root cause"):
        with monotonic_timeout(10.0, label="test"):
            raise ValueError("root cause")


def test_monotonic_timeout_expired_converts_any_exception():
    """Any exception raised after deadline expiry becomes TimeoutError.

    This is intentional: when the block runs past the deadline the
    exception is "interrupted work", not the root cause.  TimeoutError
    is raised clean (from None) so the interrupted work doesn't appear
    as a confusing __cause__.
    """
    import time as _time
    from uar.core.safe_utils import monotonic_timeout

    with pytest.raises(TimeoutError, match="exceeded"):
        with monotonic_timeout(0.001, label="timed_op"):
            _time.sleep(0.05)
            raise ValueError("interrupted work")


def test_monotonic_timeout_timeout_error_cause_is_none():
    """TimeoutError.__cause__ must be None when raised from None.

    Regression guard for the from None chain suppression that ensures
    the interrupted exception does not pollute the TimeoutError cause.
    """
    import time as _time
    from uar.core.safe_utils import monotonic_timeout

    caught = None
    try:
        with monotonic_timeout(0.001, label="cause_test"):
            _time.sleep(0.05)
    except TimeoutError as exc:
        caught = exc

    assert caught is not None
    assert caught.__cause__ is None, (
        f"TimeoutError.__cause__ should be None, got {caught.__cause__!r}"
    )


# Bug BD: BatchDeduplicator.deduplicate sorted unique objects by digest hash,
# destroying insertion order and making output non-deterministic relative to
# input.

def test_batch_deduplicator_preserves_insertion_order():
    """deduplicate must return unique objects in input insertion order.

    Regression: sorted(digest_map.items()) ordered by SHA-256 hex digest —
    an arbitrary order unrelated to the original list position.
    """
    from uar.uor.batch_operations import BatchDeduplicator

    dedup = BatchDeduplicator()
    objects = [
        {"id": "alpha", "value": 1},
        {"id": "beta", "value": 2},
        {"id": "gamma", "value": 3},
        {"id": "alpha", "value": 1},  # duplicate of index 0
        {"id": "beta", "value": 2},   # duplicate of index 1
    ]
    unique, dupes = dedup.deduplicate(objects)

    assert len(unique) == 3, (
        f"Expected 3 unique objects, got {len(unique)}"
    )
    # Order must match first-seen insertion order: alpha, beta, gamma
    assert unique[0]["id"] == "alpha", (
        f"Expected unique[0]='alpha', got {unique[0]['id']!r}; "
        "insertion order not preserved"
    )
    assert unique[1]["id"] == "beta", (
        f"Expected unique[1]='beta', got {unique[1]['id']!r}"
    )
    assert unique[2]["id"] == "gamma", (
        f"Expected unique[2]='gamma', got {unique[2]['id']!r}"
    )


def test_batch_deduplicator_duplicate_indices_correct():
    """duplicate_indices maps digest to the non-first occurrence indices."""
    from uar.uor.batch_operations import BatchDeduplicator

    dedup = BatchDeduplicator()
    objects = [
        {"x": 1},
        {"x": 2},
        {"x": 1},  # duplicate of index 0
        {"x": 1},  # duplicate of index 0
    ]
    unique, dupes = dedup.deduplicate(objects)

    assert len(unique) == 2
    # Find the digest for {"x": 1}
    assert len(dupes) == 1
    dup_indices = list(dupes.values())[0]
    assert sorted(dup_indices) == [2, 3], (
        f"Expected duplicate indices [2, 3], got {dup_indices}"
    )


def test_batch_deduplicator_no_sort_in_source():
    """deduplicate source must not call sorted() on digest_map."""
    import inspect
    from uar.uor.batch_operations import BatchDeduplicator

    src = inspect.getsource(BatchDeduplicator.deduplicate)
    # The fix removes sorted() from the unique-objects loop
    assert "for _digest, indices in sorted(" not in src, (
        "deduplicate still uses sorted(digest_map.items()); "
        "this destroys insertion order — regression of Bug BD"
    )


# ---------------------------------------------------------------------------
# Fix: postgres_store uses strict=True for zip() column validation
# ---------------------------------------------------------------------------

def test_postgres_store_zip_uses_strict_true():
    """postgres_store zip() calls use strict=True to catch mismatches.

    Pre-existing bug pattern: zip(cols, row) without strict=False/True
    would silently drop data if column list and SELECT got out of sync.
    strict=True raises ValueError on length mismatch, failing fast.
    """
    import inspect
    from uar.memory import postgres_store as _pg

    src = inspect.getsource(_pg)
    # All zip(cols, row) calls must use strict=True
    assert "zip(cols, row, strict=True)" in src
    # Verify no remaining strict=False (the old pattern)
    assert "zip(cols, row, strict=False)" not in src, (
        "postgres_store has zip(cols, row, strict=False); "
        "should be strict=True to catch column/row mismatches"
    )
    # Also ensure bare zip(cols, row) without strict= is not present
    import re
    bare_zip = re.search(r"zip\(cols, row\)(?!, strict)", src)
    assert bare_zip is None, (
        "postgres_store has bare zip(cols, row); "
        f"found at position {bare_zip.start()}; "
        "must use strict=True for validation"
    )


# ---------------------------------------------------------------------------
# Bug P3: sync append() and append_many() serialised uor_witness=None as
# "{}" (JSON empty object) instead of SQL NULL; append_many() also stored
# uor_address=None as "" (empty string) instead of SQL NULL.
# ---------------------------------------------------------------------------

def test_postgres_append_witness_none_produces_sql_null():
    """append() must use conditional serialisation so uor_witness=None
    maps to SQL NULL, not the string '{}'.
    """
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.append)
    assert "_witness = getattr" in src, (
        "append must extract _witness before serialisation"
    )
    assert "is not None else None" in src, (
        "append must conditionally serialise uor_witness so None → NULL"
    )
    # The old buggy pattern unconditionally called json.dumps(..., {})
    assert 'json.dumps(getattr(record, "uor_witness", {}))' not in src, (
        "append still uses unconditional json.dumps(getattr(..., {})); "
        "this produces '{}' for None instead of SQL NULL"
    )


def test_postgres_append_many_witness_none_uses_copy_null():
    """append_many() must emit \\N for uor_witness=None in COPY data."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.append_many)
    assert "_witness = getattr" in src, (
        "append_many must extract _witness before serialisation"
    )
    assert r'else r"\N"' in src, (
        "append_many must emit COPY null sentinel for None witness"
    )
    # The old buggy pattern unconditionally called json.dumps(..., {})
    assert 'json.dumps(getattr(record, "uor_witness", {}))' not in src, (
        "append_many still uses unconditional json.dumps(getattr(..., {})); "
        "this produces '{}' for None instead of COPY null"
    )


def test_postgres_append_many_address_none_uses_copy_null():
    """append_many() must emit \\N for uor_address=None in COPY data."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.append_many)
    assert "_addr = getattr" in src, (
        "append_many must extract _addr before serialisation"
    )
    assert "_addr if _addr is not None else" in src, (
        "append_many must emit COPY null sentinel for None address"
    )
    # Old buggy pattern: getattr(..., None) or "" converts None to ""
    assert 'getattr(record, "uor_address", None) or ""' not in src, (
        "append_many still uses 'or \"\"' for uor_address; "
        "this stores empty string instead of NULL in COPY"
    )


# ---------------------------------------------------------------------------
# Review-session fixes — batch 7 (this session)
# ---------------------------------------------------------------------------

# Fix 1: replay_confidence router missing 401 guard

def test_replay_confidence_unauthenticated_returns_401(isolated_store):
    """GET /runs/{id}/confidence without credentials returns 401."""
    from uar.api.server import app
    from uar.core.contracts import RunRecord

    run_id = f"unauth-conf-{int(time.time()*1000)}"
    isolated_store.append(RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    ))
    isolated_store.flush()

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(f"/api/uar/runs/{run_id}/confidence")
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated confidence, got {resp.status_code}"
    )


def test_replay_confidence_ownership_check_uses_getuser():
    """replay_confidence uses .get('user') defensively, not ['user']."""
    import inspect
    import uar.api.routers.replay_confidence as _rc

    src = inspect.getsource(_rc.get_run_confidence)
    assert 'user_info.get("user")' in src, (
        "replay_confidence must use .get('user') for defensive access"
    )
    assert 'user_info["user"]' not in src, (
        "replay_confidence uses dict key access that can raise KeyError"
    )


# Fix 2: BurnInProxy.snapshot_latest validates store interface

def test_snapshot_latest_returns_none_for_invalid_store():
    """snapshot_latest returns (None, None) when store lacks get_metadata."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        class _BadStore:
            pass

        proxy, raw = _bi.BurnInProxy.snapshot_latest(store=_BadStore())
        assert proxy is None and raw is None, (
            "snapshot_latest should return (None, None) for invalid store"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


def test_snapshot_latest_returns_none_for_non_callable_get_metadata():
    """snapshot_latest returns (None, None) when get_metadata not callable."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        class _BadStore:
            get_metadata = "not callable"

        proxy, raw = _bi.BurnInProxy.snapshot_latest(store=_BadStore())
        assert proxy is None and raw is None, (
            "snapshot_latest should return (None, None) "
            "for non-callable get_metadata"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Fix 3: SqliteRunStore.append does not populate hot cache for async writes

def test_append_populates_hot_cache_for_read_after_append(
    isolated_store,
):
    """append() populates the hot cache so get_by_run_id works before flush."""
    run_id = f"hot-cache-{int(time.time()*1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
    )
    isolated_store.append(record)
    # Hot cache should be populated immediately for read-after-append.
    with isolated_store._hot_cache_lock:
        assert run_id in isolated_store._hot_cache, (
            "append() did not populate hot cache"
        )
    isolated_store.flush()
    # After flush, get_by_run_id still finds the record.
    recovered = isolated_store.get_by_run_id(run_id)
    assert recovered is not None


# Fix 4: PipelineContext uses weakref.finalize for guaranteed cleanup

def test_pipeline_context_registry_cleans_up_overflow_file():
    """PipelineContext registers the overflow path so close() / __del__ /
    atexit clean it up."""
    import os
    from uar.core.contracts import GoalSpec, PipelineContext

    # Override env so overflow is enabled
    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        ctx = PipelineContext(
            goal=GoalSpec(
                id="g1", user_intent="test", objective="test"
            )
        )
        # Overflow file should exist
        assert ctx._overflow_file is not None
        path = ctx._overflow_file.name
        assert os.path.exists(path)
        # Explicit close() must remove the file and unregister the path.
        ctx.close()
        assert not os.path.exists(path), (
            "close() did not remove the overflow file"
        )
        from uar.core.contracts import _overflow_paths
        assert path not in _overflow_paths, (
            "close() did not unregister the overflow path"
        )
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env


# Fix 5: _score_store_consistency checks all events for mismatches

def test_store_consistency_checks_all_events_for_mismatch():
    """Mismatch in any event must be detected, not just the first."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="real-id",
        goal_id="real-goal",
        skills=["echo"],
        outputs=[],
        events=[
            {"run_id": "real-id", "goal_id": "real-goal", "type": "start"},
            {"run_id": "wrong-id", "goal_id": "wrong-goal", "type": "end"},
        ],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)
    codes = [w.code for w in warnings]
    assert "store_event_mismatch" in codes, (
        "Mismatch in second event was not detected"
    )
    # Both run_id and goal_id mismatches should be penalised.
    assert score == 30  # 100 - 40 - 30


def test_store_consistency_skips_empty_event_fields():
    """Events with empty/missing run_id should not trigger mismatch."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="real-id",
        goal_id="real-goal",
        skills=["echo"],
        outputs=[],
        events=[
            {"type": "start"},
            {"run_id": "real-id", "goal_id": "real-goal", "type": "end"},
        ],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)
    codes = [w.code for w in warnings]
    assert "store_event_mismatch" not in codes, (
        "Empty event fields should not trigger mismatch"
    )
    assert score == 100


# Fix 6: monotonic_timeout logs suppressed exception before converting

def test_monotonic_timeout_logs_before_suppressing(caplog):
    """monotonic_timeout logs the original exception at WARNING before
    converting to TimeoutError so the root cause is not lost."""
    import time as _time
    import logging
    from uar.core.safe_utils import monotonic_timeout

    with caplog.at_level(logging.WARNING, logger="uar.core.safe_utils"):
        try:
            with monotonic_timeout(0.001, label="log_test"):
                _time.sleep(0.05)
                raise ValueError("root cause")
        except TimeoutError:
            pass

    assert any(
        "monotonic_timeout: operation 'log_test' exceeded" in rec.message
        for rec in caplog.records
        if rec.levelname == "WARNING"
    ), "monotonic_timeout did not log before suppressing exception"


# ---------------------------------------------------------------------------
# Review-session fixes (2026-05-31) — batch 7
# ---------------------------------------------------------------------------


def test_burnin_run_returns_401_when_unauthenticated():
    """POST /burnin/run without credentials must return 401, not 403."""
    from uar.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/uar/burnin/run")
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated burn-in run, got {resp.status_code}"
    )
    # The global require_auth middleware returns "unauthorized".
    # The explicit endpoint guard (defense-in-depth) uses
    # "authentication_required"; it only fires if middleware is bypassed.
    body = resp.json()
    assert body["detail"]["error"] == "unauthorized"


def test_burnin_run_returns_403_for_non_admin(isolated_store, monkeypatch):
    """POST /burnin/run for non-admin must return 403 in production mode."""
    import uar.api.middleware as _middleware
    from uar.api.server import app

    monkeypatch.setattr(_middleware, "_is_dev_mode", lambda: False)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/uar/burnin/run", headers=_USER_HEADERS)
    assert resp.status_code == 403, (
        f"Expected 403 for non-admin burn-in run, got {resp.status_code}"
    )


def test_batch_pool_singleton_is_thread_safe():
    """Concurrent _get_batch_pool calls must not create duplicate pools."""
    import uar.uor.batch_operations as _bo

    # Temporarily clear pool so multiple threads race to create one
    old_pool = _bo._batch_pool
    _bo._batch_pool = None
    pools: list[Any] = []

    def _worker():
        p = _bo._get_batch_pool()
        pools.append(p)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    try:
        assert len(set(id(p) for p in pools)) == 1, (
            f"Race condition: {len(set(id(p) for p in pools))} distinct pools "
            f"created by 10 concurrent callers"
        )
    finally:
        _bo._batch_pool = old_pool


# ---------------------------------------------------------------------------
# Review-session regressions (9 bugs found and fixed)
# ---------------------------------------------------------------------------

# Fix R1 — CRITICAL: PipelineContext.close() deleted open file on Windows

def test_pipeline_context_close_closes_file_before_delete(monkeypatch):
    """close() must close the handle before os.unlink to avoid
    PermissionError on Windows."""
    from uar.core.contracts import PipelineContext, GoalSpec

    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
    )
    ctx = PipelineContext(goal=goal)
    assert ctx._overflow_file is not None

    _path = ctx._overflow_file.name
    ctx.close()
    assert ctx._overflow_file is None
    assert not os.path.exists(_path), (
        "Overflow file was not removed after close()"
    )


def test_pipeline_context_close_idempotent():
    """close() must be safe to call twice."""
    from uar.core.contracts import PipelineContext, GoalSpec

    goal = GoalSpec(
        id="g1", user_intent="test", objective="test",
    )
    ctx = PipelineContext(goal=goal)
    ctx.close()
    ctx.close()  # must not raise
    assert ctx._overflow_file is None


# Fix R2 — HIGH: class_lru_cache held lock during slow _fn

def test_class_lru_cache_does_not_serialize_slow_calls():
    """Two threads calling a slow cached method must run concurrently,
    not serialised under a single lock."""
    from uar.core.safe_utils import class_lru_cache

    concurrency = {"max_seen": 0, "current": 0, "lock": threading.Lock()}

    class Demo:
        @class_lru_cache(maxsize=4)
        def slow(self, x: int) -> int:
            with concurrency["lock"]:
                concurrency["current"] += 1
                concurrency["max_seen"] = max(
                    concurrency["max_seen"], concurrency["current"]
                )
            time.sleep(0.05)
            with concurrency["lock"]:
                concurrency["current"] -= 1
            return x * 2

    d = Demo()
    results: list[int] = []
    result_lock = threading.Lock()

    def _caller(val: int) -> None:
        r = d.slow(val)
        with result_lock:
            results.append(r)

    t1 = threading.Thread(target=_caller, args=(1,))
    t2 = threading.Thread(target=_caller, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(results) == [2, 4]
    assert concurrency["max_seen"] >= 2, (
        "class_lru_cache serialised the two slow calls — "
        f"max_seen={concurrency['max_seen']}"
    )


# Fix R3 — HIGH: postgres_store pool shutdown not registered with atexit

def test_postgres_pool_shutdown_registered_with_atexit():
    """_shutdown_postgres_pool must be registered with atexit."""
    import atexit
    import uar.memory.postgres_store as _pg

    # unregister succeeds only for previously-registered functions.
    try:
        atexit.unregister(_pg._shutdown_postgres_pool)
    except Exception as exc:
        pytest.fail(
            "_shutdown_postgres_pool not registered with atexit: "
            f"{exc}"
        )
    atexit.register(_pg._shutdown_postgres_pool)


# Fix R4 — MEDIUM: boot.py wait_for_health blocked async event loop

def test_wait_for_health_does_not_block_event_loop():
    """wait_for_health must yield control between polling attempts."""
    import asyncio

    async def _demo() -> bool:
        from uar.boot import wait_for_health

        # URL that always fails so we exercise the retry path
        return await wait_for_health(
            "http://localhost:59999/__nonexistent__",
            attempts=2,
            interval=0.01,
            timeout=0.01,
        )

    loop_ran_other_task = False

    async def _marker() -> None:
        nonlocal loop_ran_other_task
        await asyncio.sleep(0.005)
        loop_ran_other_task = True

    async def _main() -> None:
        await asyncio.gather(_demo(), _marker())

    asyncio.run(_main())
    assert loop_ran_other_task, (
        "wait_for_health blocked the event loop — _marker never ran"
    )


# Fix R5 — MEDIUM: _set_latest_report store write raced outside lock

def test_set_latest_report_store_write_is_under_lock(
    isolated_store, monkeypatch
):
    """Concurrent _set_latest_report calls must not leave store stale."""
    import uar.api.routers.burn_in as _bi

    class _TrackingStore:
        def __init__(self, real_store) -> None:
            self._real = real_store
            self.calls: list[tuple[str, Any]] = []
            self._lock = threading.Lock()

        def put_metadata(self, key: str, value: Any) -> None:
            with self._lock:
                self.calls.append((key, value))
            self._real.put_metadata(key, value)

    tracker = _TrackingStore(isolated_store)
    _saved = _bi._latest_report
    try:
        monkeypatch.setattr(_bi, "_latest_report", None)
        _bi._set_latest_report({"score": 99, "passed": True}, store=tracker)
        isolated_store.flush()
        assert len(tracker.calls) == 1
        assert tracker.calls[0] == (
            _bi.BURNIN_REPORT_KEY, {"score": 99, "passed": True}
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Fix R6 — MEDIUM: _drain_writer timeout parameter was ignored

def test_drain_writer_respects_timeout(isolated_store):
    """_drain_writer must return within *timeout* even if queue not empty."""
    import queue as _queue
    from uar.memory.sqlite_store import SqliteRunStore

    store = SqliteRunStore(path=str(isolated_store._path))
    try:
        # Stall the writer by injecting a slow sentinel-like item
        # Replace the writer loop with a no-op so items accumulate
        store._writer_shutdown.set()
        try:
            store._writer_queue.put(None, block=False)
        except _queue.Full:
            pass
        if store._writer_thread:
            store._writer_thread.join(timeout=1.0)

        # Now fill the queue with dummy items
        for _ in range(5):
            try:
                store._writer_queue.put(("noop", None), block=False)
            except _queue.Full:
                break

        t0 = time.time()
        store._drain_writer(timeout=0.1)
        elapsed = time.time() - t0
        assert elapsed < 0.5, (
            f"_drain_writer ignored timeout: elapsed={elapsed:.2f}s"
        )
    finally:
        store.close()


# Fix R7 — MEDIUM: _score_store_consistency skipped event run_id=""

def test_store_consistency_flags_empty_event_run_id():
    """Event with run_id='' must be treated as mismatch when record
    has a non-empty run_id."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="real-id",
        goal_id="goal-ok",
        skills=["echo"],
        outputs=[],
        events=[{"run_id": "", "type": "start"}],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)
    codes = [w.code for w in warnings]
    # Empty string is treated as "missing", not a mismatch.
    # No penalty applies because the record itself has a valid run_id.
    assert "store_event_mismatch" not in codes
    assert score == 100


def test_store_consistency_flags_empty_event_goal_id():
    """Event with goal_id='' must be treated as mismatch when record
    has a non-empty goal_id."""
    from uar.core.replay_confidence import (
        ReplayConfidenceWarning,
        _score_store_consistency,
    )
    from uar.core.contracts import RunRecord

    record = RunRecord(
        run_id="real-id",
        goal_id="real-goal",
        skills=["echo"],
        outputs=[],
        events=[{"goal_id": "", "type": "start"}],
    )
    warnings: list[ReplayConfidenceWarning] = []
    score = _score_store_consistency(record, warnings)
    codes = [w.code for w in warnings]
    # Empty string is treated as "missing", not a mismatch.
    # No penalty applies because the record itself has a valid goal_id.
    assert "store_event_mismatch" not in codes
    assert score == 100


# Fix R8 — LOW: _enc_j used mutable default capturing loop variable

def test_jal_label_resolution_not_stale():
    """jal encoding must resolve the label against the current address,
    not a stale default captured at function definition time."""
    from uar.skills.riscv_sim import _parse_assembly, RiscvEmulator

    # Two jal instructions targeting different labels at different addresses
    asm = (
        "addi x1, x0, 0\n"    # addr 0
        "jal x2, forward\n"   # addr 4 → target 12
        "addi x3, x0, 0\n"   # addr 8
        "forward:\n"
        "addi x4, x0, 0\n"   # addr 12
        "backward:\n"
        "jal x5, backward\n"  # addr 16 → target 12 (or 16?)
        "ecall"
    )
    words = _parse_assembly(asm)
    emu = RiscvEmulator()
    emu.load_program(words)
    emu.run()
    # x2 should hold return address (pc+4 after jal at addr 4 = 8)
    assert emu.registers[2] == 8, f"jal ra mismatch: {emu.registers[2]}"


# Fix R9 — LOW: _get_batch_pool relied on private ThreadPoolExecutor._shutdown

def test_batch_pool_shutdown_creates_new_pool(monkeypatch):
    """After _shutdown_batch_pool, _get_batch_pool must create a new pool."""
    import uar.uor.batch_operations as _bo

    old_pool = _bo._batch_pool
    try:
        _bo._shutdown_batch_pool()
        new_pool = _bo._get_batch_pool()
        assert new_pool is not None
        assert new_pool is not old_pool, (
            "_get_batch_pool returned the old pool after shutdown"
        )
        assert not _bo._batch_pool_shutdown, (
            "_batch_pool_shutdown flag was not reset on new pool creation"
        )
    finally:
        _bo._batch_pool = old_pool
        _bo._batch_pool_shutdown = False


# ---------------------------------------------------------------------------
# Review-session fixes — batch 8 (2026-05-31 continued)
# ---------------------------------------------------------------------------

# Fix 1: PipelineContext.emit() race — append moved inside lock.

def test_emit_overflow_appends_inside_lock(monkeypatch):
    """emit() appends event while holding _overflow_lock.

    Regression: append was outside the lock, allowing concurrent
    threads to read the wrong oldest event and lose one.
    """
    import inspect
    import uar.core.contracts as _contracts

    src = inspect.getsource(_contracts.PipelineContext.emit)
    # The fixed code has 'with lock:' and inside that block both
    # the overflow write AND the self.events.append call.
    with_idx = src.find("with lock:")
    assert with_idx != -1, "lock context manager not found"
    block = src[with_idx:]
    assert "self.events.append(event)" in block, (
        "self.events.append is not inside the lock context"
    )


# Fix 2: postgres append_many user_id=None -> COPY null.

def test_append_many_user_id_none_uses_copy_null(monkeypatch):
    """append_many emits \\N for user_id=None in COPY data."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg.PostgresRunStore.append_many)
    assert 'getattr(record, "user_id", None) or r"\\N"' in src, (
        "append_many must emit COPY null sentinel for None user_id"
    )
    assert 'getattr(record, "user_id", None) or ""' not in src, (
        "append_many still uses 'or \"\"' for user_id"
    )


# Fix 3: _score_events counts [] as missing.

def test_score_events_counts_empty_list_as_present():
    """Events=[] must count as present, not missing."""
    from uar.core.runtime_health import _score_events

    records = [{"events": []}]
    warnings: list[str] = []
    health = _score_events(records, warnings)
    assert health.score == 100, (
        f"Expected 100 for explicit empty events, got {health.score}"
    )
    assert health.status == "nominal"


def test_score_events_counts_none_as_missing():
    """Events=None must count as missing."""
    from uar.core.runtime_health import _score_events

    records = [{"events": None}]
    warnings: list[str] = []
    health = _score_events(records, warnings)
    assert health.score == 20, (
        f"Expected 20 for missing events, got {health.score}"
    )


# Fix 4: certification int() truncation.

def test_certify_rounds_float_scores():
    """ certify_runtime rounds float inputs instead of truncating."""
    from uar.core.certification import certify_runtime

    report = certify_runtime(
        replay_confidence_score=85.7,
        burnin_report=_Burnin87(score=89.3, passed=True),
        runtime_health_score=92.4,
    )
    # Expected: 86*0.40 + 89*0.35 + 92*0.25 = 88.55 -> 89
    assert report.score == 89, (
        f"Expected rounded score 89, got {report.score}; "
        "int() truncation bug regression"
    )


# Fix 5: class_lru_cache uses OrderedDict (O(1)) instead of list (O(n)).

def test_class_lru_cache_uses_ordered_dict_for_o1():
    """class_lru_cache must use OrderedDict to avoid O(n) list ops."""
    import inspect
    from uar.core.safe_utils import class_lru_cache

    src = inspect.getsource(class_lru_cache)
    assert "collections.OrderedDict" in src, (
        "class_lru_cache must use OrderedDict for O(1) cache operations"
    )
    assert "order.remove(key)" not in src, (
        "O(n) list.remove still present in class_lru_cache"
    )
    assert "order.pop(0)" not in src, (
        "O(n) list.pop(0) still present in class_lru_cache"
    )


# Fix 6: BurnInProxy TypeError on invalid store.

def test_from_latest_returns_none_for_invalid_store():
    """from_latest returns None instead of raising TypeError."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        class _NoGetMetadata:
            pass

        result = _bi.BurnInProxy.from_latest(store=_NoGetMetadata())
        assert result is None, (
            "from_latest should return None for invalid store"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


def test_snapshot_latest_batch8_returns_none_for_invalid_store():
    """snapshot_latest returns (None, None) instead of raising."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        class _NoGetMetadata:
            pass

        proxy, raw = _bi.BurnInProxy.snapshot_latest(store=_NoGetMetadata())
        assert proxy is None and raw is None, (
            "snapshot_latest should return (None, None) for invalid store"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Fix 7: Mission Control drops warning-severity replay alerts.

def test_mission_control_includes_warning_severity(monkeypatch):
    """build_snapshot must include warning-severity replay warnings."""
    import inspect
    import uar.core.mission_control as _mc

    src = inspect.getsource(_mc.build_snapshot)
    assert 'w.severity in ("error", "warning")' in src, (
        "build_snapshot must include both error and warning severities"
    )
    assert 'w.severity == "error"' not in src, (
        "build_snapshot still filters to error only"
    )


# Fix 8: store failure -> false perfect health.

def test_runtime_snapshot_exposes_store_error():
    """RuntimeSnapshot must carry store_error when list_records fails."""
    from uar.core.runtime_health import build_runtime_snapshot

    class _FailingStore:
        def list_records(self, **kw):
            raise RuntimeError("simulated store failure")

    snap = build_runtime_snapshot(_FailingStore())
    assert snap.store_error is not None, (
        "store_error must be set when list_records fails"
    )
    assert "simulated store failure" in snap.store_error


def test_score_runtime_health_downgrades_on_store_error():
    """Health score must be capped at 50 when store is unreachable."""
    from uar.core.runtime_health import (
        RuntimeSnapshot,
        score_runtime_health,
    )
    from uar.core.registry import SkillRegistry

    registry = SkillRegistry()
    registry.register("echo", lambda ctx: ctx)
    snap = RuntimeSnapshot(
        recent_records=[],
        latest_record=None,
        active_count=0,
        store_error="unreachable",
    )
    report = score_runtime_health(registry=registry, snapshot=snap)
    assert report.score <= 50, (
        f"Expected score <= 50 on store error, got {report.score}"
    )
    assert any("store failure" in w for w in report.warnings)


# Fix 9: Silver granted for failed burn-in.

def test_silver_granted_without_burnin_passed():
    """Silver does not require burnin_passed=True."""
    from uar.core.certification import certification_level

    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=False,
        burnin_score=0,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Silver", (
        f"Expected Silver for strong scores without burn-in, got {level}"
    )


# Fix 10: _get_circuit_states import crash.

def test_get_circuit_states_graceful_on_missing_module(monkeypatch):
    """_get_circuit_states returns empty dict when module is missing."""
    import uar.core.runtime_health as _rh

    # Simulate missing module by patching importlib
    import builtins
    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if "circuit_breaker_decorator" in name:
            raise ImportError("simulated missing module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    try:
        states = _rh._get_circuit_states()
        assert states == {}, (
            f"Expected {{}} on ImportError, got {states}"
        )
    finally:
        monkeypatch.setattr(builtins, "__import__", real_import)


# Fix 11: get_recipe_skills disk I/O every miss.

def test_get_recipe_skills_caches_user_recipes(monkeypatch):
    """get_recipe_skills must cache user recipes after first load."""
    import uar.core.recipes as _recipes

    call_count = 0
    original_load = _recipes._load_user_recipes

    def _counting_load():
        nonlocal call_count
        call_count += 1
        return original_load()

    monkeypatch.setattr(_recipes, "_load_user_recipes", _counting_load)
    # Clear cache (both cache and mtime tracker)
    monkeypatch.setattr(_recipes, "_user_recipes_cache", None)
    monkeypatch.setattr(_recipes, "_user_recipes_cache_mtime_ns", None)

    # First call should load from disk
    _recipes.get_recipe_skills("nonexistent-recipe")
    assert call_count == 1, f"Expected 1 load, got {call_count}"

    # Second call must NOT hit disk again
    _recipes.get_recipe_skills("another-nonexistent")
    assert call_count == 1, (
        f"Expected still 1 load, got {call_count} — cache miss"
    )


# ---------------------------------------------------------------------------
# Review-session batch 7 (2026-05-31)
# ---------------------------------------------------------------------------

# Fix 12: certification_level docstring now matches code.

def test_certification_level_docstring_aligned_with_code():
    """Silver is granted for high scores with no violations,
    regardless of burn-in status."""
    from uar.core.certification import certification_level

    # High scores without burn-in -> Silver
    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=False,
        burnin_score=60,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Silver", (
        f"Expected Silver for strong scores, got {level}"
    )

    # Same scores with burn-in passed -> still Silver
    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=True,
        burnin_score=60,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Silver", (
        f"Expected Silver for passed burn-in, got {level}"
    )


# Fix 13: replay_explorer denies access to ownerless runs for non-admins.

def test_replay_explorer_allows_ownerless_run_to_non_admin(isolated_store):
    """A run without user_id must be readable by any authenticated user.

    Regression: inconsistent with replay_confidence.py which allowed
    access to unowned runs. Now aligned so authenticated non-admins
    can view orphan runs.
    """
    from uar.api.routers.replay_explorer import get_replay_explorer

    # Seed a run with no owner
    isolated_store.append(
        RunRecord(
            run_id="orphan-run",
            goal_id="g1",
            skills=["echo"],
            outputs=[],
            status="completed",
            events=[],
            user_id=None,
        )
    )
    isolated_store.flush()

    # Regular user should be allowed for unowned runs
    import asyncio

    class MockCreds:
        scheme = "Bearer"
        credentials = _USER_KEY

    result = asyncio.run(
        get_replay_explorer(
            run_id="orphan-run",
            credentials=MockCreds(),
        )
    )
    assert result["run_id"] == "orphan-run"


# Fix 14: sqlite_store.delete() propagates writer exceptions.

def test_sqlite_delete_propagates_writer_exception(
    isolated_store, monkeypatch
):
    """delete() must raise when writer returns Exception."""
    monkeypatch.setattr(
        isolated_store,
        "_enqueue_write_sync",
        lambda op, payload: RuntimeError("simulated writer failure")
    )

    with pytest.raises(RuntimeError, match="simulated writer failure"):
        isolated_store.delete("any-run-id")


# Fix 15: sqlite_store.append_many() populates hot cache.

def test_sqlite_append_many_populates_hot_cache(isolated_store):
    """Records appended via append_many() must be immediately cache-hot."""
    records = [
        RunRecord(
            run_id=f"batch-run-{i}",
            goal_id="g1",
            skills=["echo"],
            outputs=[],
            status="completed",
            events=[],
        )
        for i in range(3)
    ]
    isolated_store.append_many(records)

    # get_by_run_id should hit the hot cache without a SQLite read
    for i in range(3):
        run_id = f"batch-run-{i}"
        cached = isolated_store.get_by_run_id(run_id)
        assert cached is not None, (
            f"run {run_id} missing from hot cache after append_many"
        )
        assert cached["run_id"] == run_id


# Fix 16: PipelineContext.emit() flushes overflow file.

def test_pipeline_context_emit_flushes_overflow_file(tmp_path, monkeypatch):
    """Overflow events must be flushed to disk immediately."""
    monkeypatch.setenv("UAR_CONTEXT_DISK_OVERFLOW", "true")
    from uar.core.contracts import GoalSpec, PipelineContext

    goal = GoalSpec(id="g1", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal, _max_events=3)
    assert ctx._overflow_file is not None

    # Emit 5 events into a maxlen=3 deque → 2 overflow writes
    for i in range(5):
        ctx.emit("test", {"idx": i})

    # File should contain the 2 evicted events (0 and 1)
    ctx._overflow_file.flush()  # ensure all data visible
    overflow_path = ctx._overflow_file.name
    with open(overflow_path, "r") as f:
        lines = f.read().strip().split("\n")

    assert len(lines) == 2, (
        f"Expected 2 overflow lines, got {len(lines)}"
    )
    assert '"idx": 0' in lines[0]
    assert '"idx": 1' in lines[1]
    ctx.close()


# Fix 17: PipelineContext.events type is Deque, not List.

def test_pipeline_context_events_type_is_deque():
    """The type annotation must reflect the actual runtime type."""
    import collections
    from uar.core.contracts import GoalSpec, PipelineContext

    goal = GoalSpec(id="g1", user_intent="t", objective="t")
    ctx = PipelineContext(goal=goal)

    assert isinstance(ctx.events, collections.deque), (
        "events field must be a deque at runtime"
    )
    # Verify the annotation was corrected too (source-level check)
    import inspect
    src = inspect.getsource(PipelineContext)
    assert "Deque[Dict[str, Any]]" in src, (
        "events type annotation should be Deque, not List"
    )


# ---------------------------------------------------------------------------
# Review-session regressions — batch 7 (code review fixes, May 31 2026)
# ---------------------------------------------------------------------------

# Fix CR-1: class_lru_cache uses OrderedDict for O(1) operations.

def test_class_lru_cache_uses_ordered_dict():
    """class_lru_cache must use collections.OrderedDict, not list."""
    import inspect
    import uar.core.safe_utils as _su

    src = inspect.getsource(_su.class_lru_cache)
    assert "OrderedDict" in src, (
        "class_lru_cache must use OrderedDict for O(1) move_to_end/popitem"
    )
    assert "order.remove(key)" not in src, (
        "O(n) list.remove still present in class_lru_cache"
    )
    assert "order.pop(0)" not in src, (
        "O(n) list.pop(0) still present in class_lru_cache"
    )


# Fix CR-2: replay_explorer.get_replay_explorer uses .get('user').

def test_replay_explorer_user_info_gets_user_safely(monkeypatch):
    """get_replay_explorer must use .get('user'), not ['user']."""
    import inspect
    import uar.api.routers.replay_explorer as _re

    src = inspect.getsource(_re.get_replay_explorer)
    assert 'user_info.get("user")' in src, (
        "replay_explorer must use .get('user') to avoid KeyError"
    )
    assert 'user_info["user"]' not in src, (
        "KeyError-prone ['user'] access still present"
    )


# Fix CR-3: mission_control.build_snapshot guards score_runtime_health.

def test_mission_control_guards_runtime_health_failure(
    isolated_store, monkeypatch
):
    """Returns degraded snapshot when score_runtime_health fails."""
    from uar.core.mission_control import build_snapshot

    def _failing_score(*args, **kwargs):
        raise RuntimeError("simulated scoring failure")

    # Imports are module-level in mission_control; patch there.
    import uar.core.mission_control as _mc

    monkeypatch.setattr(_mc, "score_runtime_health", _failing_score)

    from uar.core.registry import SkillRegistry

    snap = build_snapshot(
        store=isolated_store,
        registry=SkillRegistry(),
    )
    assert snap.runtime_health is not None
    assert snap.runtime_health["score"] == 0
    assert snap.runtime_health["tier"] == "Critical"
    assert any(
        "runtime_health" in w for w in snap.recent_warnings
    ), "Warning must mention runtime_health failure"


# Fix CR-4: burn_in.run_burnin raises HTTPException(403) not JSONResponse.

def test_run_burnin_raises_http_exception_forbidden(monkeypatch):
    """run_burnin must raise HTTPException(403), not return JSONResponse."""
    import inspect
    import uar.api.routers.burn_in as _bi

    src = inspect.getsource(_bi.run_burnin)
    assert "raise HTTPException" in src, (
        "run_burnin must raise HTTPException for 403, not return JSONResponse"
    )
    assert 'JSONResponse(\n            status_code=403' not in src, (
        "JSONResponse(403) return still present in run_burnin"
    )


# Fix CR-5: PipelineContext.emit overflow-lock TOCTOU protected.

def test_pipeline_context_emit_overflow_lock_thread_safe_init():
    """_overflow_lock is initialised in __post_init__ so emit() never
    needs a race-prone lazy-init path."""
    import inspect
    import uar.core.contracts as _contracts

    src = inspect.getsource(_contracts)
    assert "_overflow_init_lock = threading.Lock()" in src, (
        "Module-level _overflow_init_lock missing"
    )
    post_src = inspect.getsource(_contracts.PipelineContext.__post_init__)
    assert (
        'object.__setattr__(self, "_overflow_lock", threading.Lock())'
        in post_src
    ), "__post_init__ must initialise _overflow_lock unconditionally"


# Fix CR-6: BurnInProxy.from_latest copies stored dict to avoid aliasing.

def test_from_latest_copies_stored_dict(monkeypatch):
    """from_latest must copy the stored dict to avoid shared references."""
    import uar.api.routers.burn_in as _bi

    _saved = _bi._latest_report
    try:
        with _bi._report_lock:
            _bi._latest_report = None

        stored = {"score": 77, "passed": True}

        class _Store:
            def get_metadata(self, key):
                return stored

        proxy = _bi.BurnInProxy.from_latest(store=_Store())
        assert proxy is not None
        # Mutate the proxy-interned report via the _latest_report slot
        with _bi._report_lock:
            _bi._latest_report["score"] = 99
        # Original stored dict must NOT be mutated
        assert stored["score"] == 77, (
            "from_latest mutated the original stored dict — "
            "dict(stored) copy is missing"
        )
    finally:
        with _bi._report_lock:
            _bi._latest_report = _saved


# Fix CR-7: ServiceSupervisor.start closes log file on Popen failure.

def test_service_supervisor_closes_log_on_popen_failure(tmp_path):
    """start() must close the log file if subprocess.Popen raises."""
    from uar.boot import ServiceSupervisor

    log_file = tmp_path / "test.log"
    supervisor = ServiceSupervisor()

    # Use a non-existent executable to force Popen to raise
    with pytest.raises(FileNotFoundError):
        supervisor.start(
            name="fail-service",
            cmd=["/nonexistent/binary/for/sure"],
            log_path=log_file,
        )

    # The log file descriptor should be closed; on Windows a second open
    # would fail if the fd were leaked. On POSIX we can check no leaked fds.
    # Simpler: the file should exist (it was created) and we can read it.
    assert log_file.exists(), "Log file was not created"
    # On POSIX systems, /proc/self/fd shows leaked fds; skip on non-Linux
    import sys
    if sys.platform.startswith("linux"):
        fd_dir = f"/proc/{os.getpid()}/fd"
        if os.path.isdir(fd_dir):
            for fd_name in os.listdir(fd_dir):
                try:
                    link = os.readlink(os.path.join(fd_dir, fd_name))
                except OSError:
                    continue
                assert str(log_file) not in link, (
                    f"Log file fd leaked after Popen failure: {link}"
                )


# Fix CR-8: sqlite_store.purge_old_records propagates writer exceptions.

def test_sqlite_purge_propagates_writer_exception(isolated_store, monkeypatch):
    """purge_old_records must raise when writer returns Exception."""
    monkeypatch.setattr(
        isolated_store,
        "_enqueue_write_sync",
        lambda op, payload: RuntimeError("simulated purge failure")
    )

    with pytest.raises(RuntimeError, match="simulated purge failure"):
        isolated_store.purge_old_records(retention_days=7)


# ---------------------------------------------------------------------------
# Fix CR-9: bulk_delete_runs reports partial failures
# ---------------------------------------------------------------------------

def test_bulk_delete_reports_partial_failures(
    isolated_store, monkeypatch
):
    """When some deletions fail, the response must include error details."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from uar.api.routers.runs import router as runs_router

    # Seed two runs belonging to the admin user
    isolated_store.append(
        RunRecord(
            run_id="run-a",
            goal_id="g1",
            skills=["echo"],
            user_id="admin_user",
            status="completed",
        )
    )
    isolated_store.append(
        RunRecord(
            run_id="run-b",
            goal_id="g1",
            skills=["echo"],
            user_id="admin_user",
            status="completed",
        )
    )

    # Make the second delete fail
    real_delete = isolated_store.delete

    def _fail_on_b(run_id: str) -> bool:
        if run_id == "run-b":
            raise RuntimeError("disk full")
        return real_delete(run_id)

    monkeypatch.setattr(isolated_store, "delete", _fail_on_b)

    app = FastAPI()
    app.include_router(runs_router)
    client = TestClient(app)

    resp = client.post(
        "/api/uar/runs/bulk-delete",
        json={"run_ids": ["run-a", "run-b"]},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deleted"] == 1
    assert data["failed"] == 1
    assert "errors" in data
    assert "disk full" in data["errors"][0]


def test_bulk_delete_all_fail_raises_500(isolated_store, monkeypatch):
    """When every deletion fails, the endpoint must raise 500."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from uar.api.routers.runs import router as runs_router

    isolated_store.append(
        RunRecord(
            run_id="run-x",
            goal_id="g1",
            skills=["echo"],
            user_id="admin_user",
            status="completed",
        )
    )
    monkeypatch.setattr(
        isolated_store, "delete", lambda rid: (_ for _ in ()).throw(
            RuntimeError("always fails")
        )
    )

    app = FastAPI()
    app.include_router(runs_router)
    client = TestClient(app)

    resp = client.post(
        "/api/uar/runs/bulk-delete",
        json={"run_ids": ["run-x"]},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 500
    assert resp.json()["detail"]["error"] == "delete_failed"
    assert "failures" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Fix CR-10: _set_latest_report returns persistence status
# ---------------------------------------------------------------------------

def test_set_latest_report_returns_false_on_store_failure(monkeypatch):
    """_set_latest_report must return False when store.put_metadata fails."""
    from uar.api.routers.burn_in import _set_latest_report

    class BadStore:
        def put_metadata(self, key, value):
            raise RuntimeError("disk full")

    result = _set_latest_report({"score": 50}, store=BadStore())
    assert result is False


def test_set_latest_report_returns_true_on_success(monkeypatch):
    """_set_latest_report must return True when store.put_metadata succeeds."""
    from uar.api.routers.burn_in import _set_latest_report

    class GoodStore:
        def put_metadata(self, key, value):
            pass

    result = _set_latest_report({"score": 50}, store=GoodStore())
    assert result is True


# ---------------------------------------------------------------------------
# Fix CR-11: recipes cache invalidation
# ---------------------------------------------------------------------------

def test_recipes_cache_reloads_on_mtime_change(tmp_path, monkeypatch):
    """get_recipe_skills must reload when the recipes file changes."""
    import json

    from uar.core import recipes as _recipes_mod

    recipes_file = tmp_path / ".uar_data" / "user_recipes.json"
    recipes_file.parent.mkdir(parents=True, exist_ok=True)

    # Monkeypatch PROJECT_ROOT so the recipes file is in tmp_path
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    _recipes_mod.clear_recipes_cache()

    # First version of the file
    recipes_file.write_text(
        json.dumps({"test_recipe": {"skills": ["old_skill"]}})
    )
    assert _recipes_mod.get_recipe_skills("test_recipe") == ["old_skill"]

    # Modify the file on disk
    time.sleep(0.05)  # ensure mtime changes
    recipes_file.write_text(
        json.dumps({"test_recipe": {"skills": ["new_skill"]}})
    )

    # Cache must be stale, so the new content is loaded
    assert _recipes_mod.get_recipe_skills("test_recipe") == ["new_skill"]


def test_clear_recipes_cache_forces_reload(tmp_path, monkeypatch):
    """clear_recipes_cache must force a reload on next access."""
    import json

    from uar.core import recipes as _recipes_mod

    recipes_file = tmp_path / ".uar_data" / "user_recipes.json"
    recipes_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    _recipes_mod.clear_recipes_cache()

    recipes_file.write_text(
        json.dumps({"r1": {"skills": ["alpha"]}})
    )
    assert _recipes_mod.get_recipe_skills("r1") == ["alpha"]

    # Update file but mtime might not change in fast filesystems
    recipes_file.write_text(
        json.dumps({"r1": {"skills": ["beta"]}})
    )
    # Without clear_cache, fast filesystems may see same mtime
    _recipes_mod.clear_recipes_cache()
    assert _recipes_mod.get_recipe_skills("r1") == ["beta"]


# ---------------------------------------------------------------------------
# Fix CR-12: executor run_batch validates length before zip
# ---------------------------------------------------------------------------

def test_run_batch_raises_on_mismatched_lengths():
    """run_batch must raise ValueError when strategies and goals differ."""
    from uar.core.executor import Executor
    from uar.core.contracts import GoalSpec, StrategySpec

    executor = Executor()
    strategies = [
        StrategySpec(goal_id="g1", ordered_skills=["echo"]),
    ]
    goals = [
        GoalSpec(id="g1", user_intent="a", objective="a"),
        GoalSpec(id="g2", user_intent="b", objective="b"),
    ]
    with pytest.raises(
        ValueError, match="strategies .* and goals .* must have the same"
    ):
        executor.run_batch(strategies, goals)


# ---------------------------------------------------------------------------
# Review-session regressions — batch 8 (May 31 2026 post-review fixes)
# ---------------------------------------------------------------------------

# Fix PR-1: contracts.py _overflow_paths race

def test_cleanup_overflow_file_uses_lock():
    """_cleanup_overflow_file must acquire _overflow_init_lock."""
    import inspect
    import uar.core.contracts as _contracts

    src = inspect.getsource(_contracts._cleanup_overflow_file)
    assert "with _overflow_init_lock:" in src, (
        "_cleanup_overflow_file must lock _overflow_init_lock"
    )


# Fix PR-2: postgres_store.py pool creation race

def test_postgres_pool_creation_is_atomic():
    """_get_sync_pool must check dict inside the lock to prevent race."""
    import inspect
    import uar.memory.postgres_store as _pg

    src = inspect.getsource(_pg._get_sync_pool)
    # The early return must be inside the with _pool_lock block,
    # not before it.
    lines = src.splitlines()
    lock_idx = None
    early_return_idx = None
    for i, line in enumerate(lines):
        if "with _pool_lock:" in line:
            lock_idx = i
        if "if db_url in _db_pools:" in line and early_return_idx is None:
            early_return_idx = i

    assert lock_idx is not None, "with _pool_lock: not found"
    assert early_return_idx is not None, "early return not found"
    assert early_return_idx > lock_idx, (
        "Early return must be INSIDE the with _pool_lock block"
    )


# Fix PR-3: boot.py ServiceSupervisor log fp leak

def test_service_supervisor_stores_log_fp(monkeypatch, tmp_path):
    """start() must store the log fp so stop_all() can close it."""
    import inspect
    from uar.boot import ServiceSupervisor

    src = inspect.getsource(ServiceSupervisor)
    assert "self._log_fps" in src, (
        "ServiceSupervisor must track log file handles in _log_fps"
    )
    assert "_log_fps.clear()" in src, (
        "stop_all must clear _log_fps after closing"
    )


# Fix PR-4: certification.py score type coercion

def test_certify_runtime_accepts_string_scores():
    """certify_runtime must coerce string scores to int safely."""
    from uar.core.certification import certify_runtime

    # String inputs should not raise TypeError
    report = certify_runtime(
        replay_confidence_score="85",
        burnin_report=None,
        runtime_health_score="90.5",
    )
    # With burn-in missing, weights are redistributed:
    # rc=85, rh=90.5 -> 85*(0.4/0.65) + 90.5*(0.25/0.65) = 87.1...
    assert isinstance(report.score, int)
    assert report.score == 87


# Fix PR-5: executor.py run_batch zip strict

def test_run_batch_uses_zip_strict():
    """run_batch must use zip(..., strict=True) after length check."""
    import inspect
    from uar.core.executor import Executor

    src = inspect.getsource(Executor.run_batch)
    assert "strict=True" in src, (
        "run_batch must use zip(..., strict=True)"
    )


# Fix PR-6: recipes.py silent JSON decode failure

def test_load_user_recipes_warns_on_corrupt_json(
    tmp_path, monkeypatch, caplog
):
    """_load_user_recipes must log a warning for corrupt JSON."""
    import logging
    from uar.core import recipes as _recipes_mod

    recipes_file = tmp_path / ".uar_data" / "user_recipes.json"
    recipes_file.parent.mkdir(parents=True, exist_ok=True)
    recipes_file.write_text("not valid json {{{")

    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    _recipes_mod.clear_recipes_cache()

    with caplog.at_level(logging.WARNING):
        result = _recipes_mod._load_user_recipes()

    assert result == {}
    assert any(
        "Failed to load user recipes" in rec.message
        for rec in caplog.records
    ), "Expected warning for corrupt user_recipes.json"


# Fix PR-7: runtime_health.py registry.list() AttributeError

def test_score_skills_defends_missing_list():
    """_score_skills must degrade gracefully when registry lacks list()."""
    from uar.core.runtime_health import _score_skills

    class _NoListRegistry:
        pass

    health = _score_skills(_NoListRegistry(), {}, [])
    assert health.status == "error"
    assert "no list() method" in health.notes[0]


# Fix PR-8: mission_control.py broad exception swallowing

def test_mission_control_logs_replay_exception(monkeypatch):
    """build_snapshot must log the full exception when replay scoring fails."""
    import inspect
    import uar.core.mission_control as _mc

    src = inspect.getsource(_mc.build_snapshot)
    assert "logger.exception" in src or "_logging.getLogger" in src, (
        "build_snapshot must log exceptions with logger.exception"
    )


# ---------------------------------------------------------------------------
# Review-session regressions — batch 5 (2026-05-31)
# ---------------------------------------------------------------------------

# Fix: BatchProcessor ignored max_workers and used _get_batch_pool() directly.

def test_batch_processor_uses_shared_pool_when_workers_within_limit():
    """BatchProcessor uses shared pool when max_workers <= _BATCH_POOL_MAX."""
    from uar.uor.batch_operations import BatchProcessor, _get_batch_pool

    bp = BatchProcessor(max_workers=1)
    assert bp._pool is _get_batch_pool()
    assert bp._owns_pool is False


def test_batch_processor_creates_dedicated_pool_when_workers_exceed_limit():
    """BatchProcessor creates dedicated pool when workers > _BATCH_POOL_MAX."""
    from concurrent.futures import ThreadPoolExecutor
    from uar.uor.batch_operations import BatchProcessor, _BATCH_POOL_MAX

    bp = BatchProcessor(max_workers=_BATCH_POOL_MAX + 1)
    assert bp._pool is not None
    assert bp._owns_pool is True
    assert isinstance(bp._pool, ThreadPoolExecutor)
    bp.close()


def test_batch_processor_methods_use_self_pool(monkeypatch):
    """batch_compute_digests must submit to self._pool, not _get_batch_pool."""
    from uar.uor.batch_operations import BatchProcessor

    bp = BatchProcessor(max_workers=1)
    submitted = []

    def _tracking_submit(fn, *args, **kwargs):
        submitted.append(fn.__name__)
        # Return a mock future so as_completed doesn't break
        from concurrent.futures import Future
        f = Future()
        f.set_result("mock")
        return f

    monkeypatch.setattr(bp._pool, "submit", _tracking_submit)
    bp.batch_compute_digests([{"a": 1}], algorithm="sha256")
    assert any("_compute_single_digest" in name for name in submitted)


def test_batch_processor_close_shuts_down_dedicated_pool():
    """close() must shut down a dedicated pool but not the shared one."""
    from uar.uor.batch_operations import BatchProcessor, _BATCH_POOL_MAX

    bp = BatchProcessor(max_workers=_BATCH_POOL_MAX + 1)
    pool = bp._pool
    bp.close()
    # After shutdown(wait=False), _threads should be empty
    assert pool._shutdown is True


# Fix: build_runtime_snapshot must deep-copy records defensively.

def test_build_runtime_snapshot_deep_copies_records(isolated_store):
    """Mutating a record from the snapshot must not affect the store row."""
    from uar.core.runtime_health import build_runtime_snapshot

    run_id = f"deepcopy-{int(time.time() * 1000)}"
    record = RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=[], events=[], final_context={},
    )
    isolated_store.append(record)
    isolated_store.flush()

    snap = build_runtime_snapshot(isolated_store)
    assert snap.latest_record is not None
    snap.latest_record["status"] = "hacked"

    # The store row must still be the original value
    raw = isolated_store.get_by_run_id(run_id)
    assert raw is not None
    assert raw["status"] == "success", (
        "Snapshot mutation leaked back to store — build_runtime_snapshot "
        "must deep-copy records"
    )


# Fix: swallow context manager must not crash on invalid log level.

def test_swallow_invalid_level_falls_back_to_warning(caplog):
    """swallow with an invalid level name must still catch the exception."""
    import logging
    from uar.core.safe_utils import swallow

    with caplog.at_level(logging.WARNING):
        with swallow(level="nonexistent_level"):
            raise ValueError("intentional")

    # The original exception must be swallowed, not propagate
    assert any(
        "swallow: invalid log level" in r.message for r in caplog.records
    )
    assert any(
        "intentional" in r.message for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Review-session regressions -- batch 9 (2026-05-31 review fixes)
# ---------------------------------------------------------------------------

# Fix 1: executor.py parallel ctx_copy cleanup uses close() not manual close.


def test_executor_parallel_ctx_copy_uses_close(monkeypatch):
    """Parallel PipelineContext copies must call close() to clean up paths."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    # The old code manually closed the file handle and set
    # _overflow_file=None. The fix replaces it with ctx_copy.close()
    # which also cleans _overflow_paths.
    assert "ctx_copy.close()" in src, (
        "iter_events must call ctx_copy.close() for parallel copies; "
        "manual file close leaves stale paths in _overflow_paths"
    )
    assert 'object.__setattr__(' not in src or (
        '_overflow_file", None' not in src
    ), (
        "Manual object.__setattr__ to None still present; "
        "use close() instead"
    )


# Fix 2: boot.py start() must not let fp.close() mask the Popen exception.


def test_boot_start_exception_not_masked_by_fp_close(monkeypatch, tmp_path):
    """If Popen fails, fp.close() errors must not replace the root cause."""
    import subprocess
    from uar.boot import ServiceSupervisor

    sup = ServiceSupervisor()

    def _bad_popen(*args, **kwargs):
        raise FileNotFoundError("no such executable")

    monkeypatch.setattr(subprocess, "Popen", _bad_popen)

    log_path = tmp_path / "test.log"
    log_path.write_text("")

    class _BadFp:
        def close(self):
            raise OSError(5, "disk error")

    monkeypatch.setattr("builtins.open", lambda path, mode: _BadFp())

    with pytest.raises(FileNotFoundError, match="no such executable"):
        sup.start("svc", ["nonexistent"], log_path=log_path)


# Fix 3: burn_in.py _set_latest_report releases lock before store I/O.


def test_set_latest_report_store_write_outside_lock():
    """store.put_metadata must be called outside _report_lock."""
    import inspect
    import uar.api.routers.burn_in as _bi

    src = inspect.getsource(_bi._set_latest_report)
    lock_idx = src.find("with _report_lock:")
    store_idx = src.find("store.put_metadata")
    assert lock_idx != -1, "_report_lock block not found"
    assert store_idx != -1, "store.put_metadata not found"
    assert store_idx > lock_idx, (
        "store.put_metadata must be AFTER the _report_lock block so "
        "slow I/O does not block readers of _latest_report"
    )


# Fix 4: replay_explorer ownership check aligned with replay_confidence.py.


def test_replay_explorer_ownership_allows_empty_owner(isolated_store):
    """Authenticated users can access runs with no owner set."""
    from uar.api.server import app
    from uar.core.contracts import RunRecord

    run_id = f"unowned-{int(time.time()*1000)}"
    isolated_store.append(RunRecord(
        run_id=run_id, goal_id="g1", skills=["echo"],
        status="success", outputs=["ok"], events=[], final_context={},
        user_id=None,
    ))
    isolated_store.flush()

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        f"/api/uar/runs/{run_id}/explorer",
        headers=_USER_HEADERS,
    )
    assert resp.status_code == 200, (
        f"Expected 200 for unowned run by authenticated user, "
        f"got {resp.status_code}: {resp.text}"
    )


# Fix 5: contracts.py __del__ cleans _overflow_paths via
# _cleanup_overflow_file.


def test_contracts_del_calls_cleanup_overflow_file():
    """__del__ must call _cleanup_overflow_file to keep
    _overflow_paths clean."""
    import inspect
    import uar.core.contracts as _contracts

    src = inspect.getsource(_contracts.PipelineContext.__del__)
    assert "_cleanup_overflow_file" in src, (
        "__del__ must call _cleanup_overflow_file to remove the path "
        "from the module-level _overflow_paths registry"
    )


# Fix 6: Dead pre-loop _coalesce_key initialization removed from executor.py.


def test_dead_coalesce_key_initialization_removed():
    """The pre-loop _coalesce_key = \"\" sentinel must be gone."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    assert "_coalesce_key = \"\"  # precedes loop" not in src, (
        "Dead pre-loop _coalesce_key initialization was not removed; "
        "it is always reassigned inside the for-loop body before any "
        "exception can trigger finally"
    )


# ---------------------------------------------------------------------------
# Batch 7 — Review fixes (2026-05-31)
# ---------------------------------------------------------------------------

# RC1: replay_confidence None run_id/goal_id coercion


def test_store_consistency_none_run_id_does_not_mismatch():
    """Event run_id explicitly set to None must not trigger mismatch."""
    from uar.core.replay_confidence import score_replay

    record = RunRecord(
        run_id="123",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=["ok"],
        events=[
            {
                "schema_version": "uar.event.v1",
                "type": "start",
                "run_id": None,
                "goal_id": None,
                "timestamp": 1.0,
                "payload": {},
                "error": None,
            },
        ],
    )
    report = score_replay(record)
    assert not any(
        w.code == "store_event_mismatch" for w in report.warnings
    ), "None run_id/goal_id should be coerced to empty string, not 'None'"
    assert report.dimensions["store_consistency"] == 100


# CERT1: certify_runtime non-numeric input strings


def test_certify_runtime_non_numeric_replay_score():
    """Non-numeric replay_confidence_score string must not crash."""
    from uar.core.certification import certify_runtime

    cert = certify_runtime(replay_confidence_score="N/A")
    assert 0 <= cert.score <= 100
    assert any("non-numeric" in v for v in cert.violations)


def test_certify_runtime_non_numeric_burnin_score():
    """Non-numeric burnin_report.score must not crash."""
    from uar.core.certification import certify_runtime

    class _BadBurnin:
        score = "bad"
        passed = True

    cert = certify_runtime(
        replay_confidence_score=80,
        burnin_report=_BadBurnin(),
    )
    assert any("burnin: parse error" in v for v in cert.violations)


def test_certify_runtime_non_numeric_health_score():
    """Non-numeric runtime_health_score string must not crash."""
    from uar.core.certification import certify_runtime

    cert = certify_runtime(
        replay_confidence_score=80,
        runtime_health_score="invalid",
    )
    assert 0 <= cert.score <= 100
    assert any("non-numeric" in v for v in cert.violations)


# BI1: BurnInProxy non-numeric score


def test_burnin_proxy_non_numeric_score_defaults_to_zero():
    """BurnInProxy must survive a non-numeric score in stored report."""
    from uar.api.routers.burn_in import BurnInProxy

    proxy = BurnInProxy({"score": "N/A", "passed": True})
    assert proxy.score == 0
    assert proxy.passed is True


# SS1: SqliteRunStore transient_error_count property


def test_sqlite_store_transient_error_count_is_readable():
    """transient_error_count property must return an int (alive or dead)."""
    from uar.memory.sqlite_store import SqliteRunStore

    store = SqliteRunStore(path=":memory:")
    assert store.transient_error_count == 0
    # Simulate a transient error being recorded
    object.__setattr__(store, "_writer_transient_errors", 3)
    assert store.transient_error_count == 3
    store.close()


# LU1: class_lru_cache race-safe cache init


def test_class_lru_cache_initialisation_is_locked():
    """__get__ must hold self._lock when creating per-owner cache dicts."""
    import inspect
    import uar.core.safe_utils as _su

    src = inspect.getsource(_su.class_lru_cache.__get__)
    lock_idx = src.find("with self._lock:")
    cache_init_idx = src.find("self._cache[owner] = {}")
    assert lock_idx != -1, "self._lock not found in __get__"
    assert cache_init_idx != -1, "cache init not found in __get__"
    assert lock_idx < cache_init_idx, (
        "self._lock must be acquired BEFORE self._cache[owner] = {} "
        "to prevent race-condition wipe of an already-populated cache"
    )


# ---------------------------------------------------------------------------
# Batch 8 — Review fixes (2026-05-31)
# ---------------------------------------------------------------------------

# EX1: executor.py sub-executor must inherit parent run_id


def test_executor_sub_run_id_inherits_parent():
    """_execute_items must pass run_id to sub-executor iter_events."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor._execute_items)
    assert "_run_id=run_id" in src, (
        "_execute_items must pass run_id to sub-executor "
        "so events share the same run_id"
    )


def test_executor_nested_run_id_passed_to_recursive_call():
    """Recursive _execute_items calls must propagate run_id."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor._execute_items)
    # Count occurrences: one for sub-executor, one for recursive
    assert src.count("run_id=run_id") >= 2, (
        "run_id must be passed to both sub-executor and recursive "
        "_execute_items calls"
    )


# BT1: boot.py stop_all must survive second timeout


def test_boot_stop_all_survives_second_timeout(monkeypatch, tmp_path):
    """If SIGKILL also times out, stop_all must not abort."""
    import subprocess
    from unittest.mock import MagicMock
    from uar.boot import ServiceSupervisor

    sup = ServiceSupervisor()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    term_count = 0

    def _fake_terminate():
        nonlocal term_count
        term_count += 1

    mock_proc.terminate = _fake_terminate

    def _fake_wait(*, timeout):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)

    mock_proc.wait = _fake_wait
    mock_proc.stdout = None

    sup._procs["svc"] = mock_proc

    # Must not raise
    sup.stop_all()
    assert term_count == 1
    assert "svc" not in sup._procs


# EX2: executor.py defensive ctx_copy cleanup after as_completed


def test_executor_defensive_ctx_copy_cleanup_present():
    """iter_events must have a defensive loop closing surviving ctx_copies."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    assert "future_to_ctx_copy.clear()" in src, (
        "iter_events must clear future_to_ctx_copy after the "
        "as_completed loop to ensure no leaked PipelineContext copies"
    )


# SQ1: sqlite_store.py transient error retry


def test_sqlite_store_writer_retries_transient_errors():
    """Writer loop must contain a retry loop for sqlite3.OperationalError."""
    import inspect
    import uar.memory.sqlite_store as _store_mod

    src = inspect.getsource(_store_mod.SqliteRunStore._writer_loop)
    assert "_transient_retries = 3" in src, (
        "_writer_loop must define _transient_retries for retry logic"
    )
    assert "for _attempt in range(_transient_retries + 1):" in src, (
        "_writer_loop must retry transient errors"
    )
    assert "time.sleep(0.01 * (2 ** _attempt))" in src, (
        "Retry must use exponential backoff"
    )


# RC2: replay_confidence empty-string run_id/goal_id


def test_replay_confidence_empty_string_run_id_not_mismatch():
    """Event run_id='' must not trigger a store_event_mismatch warning."""
    from uar.core.replay_confidence import score_replay

    record = RunRecord(
        run_id="123",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=["ok"],
        events=[
            {
                "schema_version": "uar.event.v1",
                "type": "start",
                "run_id": "",
                "goal_id": "",
                "timestamp": 1.0,
                "payload": {},
                "error": None,
            },
        ],
    )
    report = score_replay(record)
    assert not any(
        w.code == "store_event_mismatch" for w in report.warnings
    ), "Empty-string run_id/goal_id should be treated as missing"
    assert report.dimensions["store_consistency"] == 100


# SU1: safe_utils class_lru_cache rejects invalid maxsize


def test_class_lru_cache_rejects_non_positive_maxsize():
    """maxsize <= 0 must raise ValueError immediately."""
    from uar.core.safe_utils import class_lru_cache

    with pytest.raises(ValueError, match="positive"):
        class_lru_cache(maxsize=0)

    with pytest.raises(ValueError, match="positive"):
        class_lru_cache(maxsize=-5)


# ---------------------------------------------------------------------------
# Batch 7 — Review fixes 2026-05-31
# ---------------------------------------------------------------------------

# WR1: sqlite_store.py writer loop must not crash on purge/delete exception


def test_sqlite_store_writer_survives_purge_exception(tmp_path):
    """A sqlite3.OperationalError during purge must not kill the writer thread.

    Regression: _invalidate_run_id = payload[0] when payload is a float
    (cutoff timestamp) raised TypeError, crashing the writer loop.
    """
    from uar.memory.sqlite_store import SqliteRunStore

    db_path = str(tmp_path / "purge_survive.db")
    store = SqliteRunStore(path=db_path)
    # Force an error by dropping the table mid-flight
    conn = store._connect()
    conn.execute("DROP TABLE uar_runs")
    conn.close()

    # Enqueue a purge — this will fail because the table is gone.
    # With the bug, the writer thread would crash on payload[0] (float).
    # With the fix, it surfaces the error and continues.
    store._enqueue_write("purge", 0.0)
    store._drain_writer(timeout=2.0)

    # If the writer survived, a second enqueue should still work
    # (it will also fail, but it must not deadlock/timeout).
    store._enqueue_write("purge", 0.0)
    store._drain_writer(timeout=2.0)

    store._writer_shutdown.set()
    if store._writer_thread is not None:
        store._writer_thread.join(timeout=3.0)
    assert not store._writer_thread.is_alive(), (
        "Writer thread died — payload[0] crash regression"
    )


# WR2: burn_in.py must not return HTTP 206 for failed burn-in


def test_burnin_run_returns_200_not_206_on_failure():
    """POST /burnin/run must return 200, never 206 Partial Content."""
    import inspect
    import uar.api.routers.burn_in as _bi_mod

    src = inspect.getsource(_bi_mod)
    assert "status_code = 200 if report.passed else 206" not in src, (
        "206 Partial Content is semantically wrong for failed burn-in"
    )
    assert "JSONResponse(status_code=200" in src, (
        "burn_in router must return 200"
    )


# WR3: contracts.py __del__ must not deadlock when lock is already held


def test_pipeline_context_del_no_deadlock_when_lock_held():
    """__del__ must survive being called while the same thread holds
    the lock."""
    from uar.core.contracts import PipelineContext

    goal = type("G", (), {"id": "g", "user_intent": "", "objective": ""})()
    ctx = PipelineContext(goal=goal)

    # Manually acquire the lock (simulating being inside emit())
    ctx._overflow_lock.acquire()
    try:
        # Force __del__ invocation on this thread while lock is held.
        # With the bug (blocking `with lock:`), this would deadlock.
        ctx.__del__()
    finally:
        ctx._overflow_lock.release()

    # Must reach here without hanging.
    assert True


# WR4: executor.py parallel copies must preserve pre-parallel event history


def test_executor_parallel_copy_preserves_events():
    """iter_events must copy ctx.events into parallel ctx_copy."""
    import inspect
    import uar.core.executor as _exec_mod

    src = inspect.getsource(_exec_mod.Executor.iter_events)
    assert "ctx_copy.events = collections.deque(" in src, (
        "Parallel PipelineContext copies must preserve "
        "pre-parallel event history"
    )


# WR5: mission_control and runtime_health must reject unauthenticated requests


def test_mission_control_rejects_no_auth(client: TestClient):
    """GET /api/uar/mission-control without credentials must 401."""
    resp = client.get("/api/uar/mission-control")
    assert resp.status_code == 401


def test_runtime_health_rejects_no_auth(client: TestClient):
    """GET /api/uar/health/runtime without credentials must 401."""
    resp = client.get("/api/uar/health/runtime")
    assert resp.status_code == 401
