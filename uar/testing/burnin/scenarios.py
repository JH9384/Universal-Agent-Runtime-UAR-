"""Burn-In smoke scenario definitions.

Each scenario is a pure function that accepts a context dict and returns
a BurnInEvidence. Context keys differ between direct and HTTP modes.

Direct mode context:
    store       — RunStore instance
    registry    — SkillRegistry instance
    executor    — Executor instance (optional)

HTTP mode context:
    base_url    — str, e.g. "http://localhost:8000"
    client      — httpx.Client instance

Trust Spine Phase: T3
Issue: #62
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from uar.testing.burnin.contracts import BurnInEvidence

ScenarioFn = Callable[[Dict[str, Any]], BurnInEvidence]


def _scenario_api_reachable_direct(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """Verify skill registry is populated (direct mode)."""
    try:
        registry = ctx["registry"]
        skills = registry.list()
        if skills:
            return BurnInEvidence(
                scenario="api_reachable",
                passed=True,
                detail=f"Registry has {len(skills)} skills",
                score=100,
            )
        return BurnInEvidence(
            scenario="api_reachable",
            passed=False,
            detail="Registry is empty",
            score=0,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="api_reachable",
            passed=False,
            detail=f"Registry check failed: {exc}",
            score=0,
        )


def _scenario_api_reachable_http(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """GET /api/health returns 200 (HTTP mode)."""
    try:
        client = ctx["client"]
        base_url = ctx["base_url"].rstrip("/")
        resp = client.get(f"{base_url}/api/health", timeout=5)
        if resp.status_code == 200:
            return BurnInEvidence(
                scenario="api_reachable",
                passed=True,
                detail=f"GET /api/health → {resp.status_code}",
                score=100,
            )
        return BurnInEvidence(
            scenario="api_reachable",
            passed=False,
            detail=f"GET /api/health → {resp.status_code}",
            score=0,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="api_reachable",
            passed=False,
            detail=f"HTTP error: {exc}",
            score=0,
        )


def _scenario_store_round_trip_direct(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """Append a RunRecord and retrieve it (direct mode)."""
    import time as _time

    from uar.core.contracts import RunRecord

    try:
        store = ctx["store"]
        run_id = f"burnin-smoke-{int(_time.time() * 1000)}"
        record = RunRecord(
            run_id=run_id,
            goal_id="burnin-goal",
            skills=["echo"],
            status="success",
            outputs=["burnin-ok"],
        )
        store.append(record)
        retrieved = store.get_by_run_id(run_id)
        if retrieved and retrieved.get("run_id") == run_id:
            return BurnInEvidence(
                scenario="store_round_trip",
                passed=True,
                detail=f"Stored and retrieved run {run_id}",
                score=100,
            )
        return BurnInEvidence(
            scenario="store_round_trip",
            passed=False,
            detail=f"Retrieved record missing or mismatched for {run_id}",
            score=0,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="store_round_trip",
            passed=False,
            detail=f"Store round-trip failed: {exc}",
            score=0,
        )


def _scenario_store_round_trip_http(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """POST a run, then GET it back (HTTP mode)."""
    try:
        client = ctx["client"]
        base_url = ctx["base_url"].rstrip("/")
        run_id = ctx.get("_last_run_id")
        if not run_id:
            return BurnInEvidence(
                scenario="store_round_trip",
                passed=False,
                detail="No run_id from run_executes scenario",
                score=0,
            )
        resp = client.get(
            f"{base_url}/api/uar/runs/{run_id}", timeout=5
        )
        if resp.status_code == 200:
            return BurnInEvidence(
                scenario="store_round_trip",
                passed=True,
                detail=f"GET /api/uar/runs/{run_id} → 200",
                score=100,
            )
        return BurnInEvidence(
            scenario="store_round_trip",
            passed=False,
            detail=f"GET /api/uar/runs/{run_id} → {resp.status_code}",
            score=0,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="store_round_trip",
            passed=False,
            detail=f"HTTP error: {exc}",
            score=0,
        )


def _scenario_replay_confidence_direct(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """Score replay confidence on a freshly stored record (direct mode)."""
    import time as _time

    from uar.core.contracts import RunRecord
    from uar.core.replay_confidence import score_replay

    try:
        store = ctx["store"]
        run_id = f"burnin-rc-{int(_time.time() * 1000)}"
        events = [
            {
                "schema_version": "uar.event.v1",
                "type": "start",
                "run_id": run_id,
                "goal_id": "burnin-goal",
                "skill": None,
                "timestamp": _time.time(),
                "payload": {"skills": ["echo"]},
                "error": None,
            },
            {
                "schema_version": "uar.event.v1",
                "type": "complete",
                "run_id": run_id,
                "goal_id": "burnin-goal",
                "skill": None,
                "timestamp": _time.time() + 0.1,
                "payload": {
                    "status": "success",
                    "outputs": ["ok"],
                    "errors": [],
                    "final_context": {},
                },
                "error": None,
            },
        ]
        record = RunRecord(
            run_id=run_id,
            goal_id="burnin-goal",
            skills=["echo"],
            status="success",
            outputs=["ok"],
            events=events,
            final_context={},
        )
        store.append(record)
        report = score_replay(record)
        if report.tier in ("Verified", "High", "Medium"):
            return BurnInEvidence(
                scenario="replay_confidence",
                passed=True,
                detail=(
                    f"Replay confidence {report.tier} "
                    f"(score={report.score})"
                ),
                score=report.score,
            )
        return BurnInEvidence(
            scenario="replay_confidence",
            passed=False,
            detail=(
                f"Replay confidence {report.tier} "
                f"(score={report.score})"
            ),
            score=report.score,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="replay_confidence",
            passed=False,
            detail=f"Replay confidence check failed: {exc}",
            score=0,
        )


def _scenario_replay_confidence_http(
    ctx: Dict[str, Any],
) -> BurnInEvidence:
    """GET replay confidence for last run (HTTP mode)."""
    try:
        client = ctx["client"]
        base_url = ctx["base_url"].rstrip("/")
        run_id = ctx.get("_last_run_id")
        if not run_id:
            return BurnInEvidence(
                scenario="replay_confidence",
                passed=False,
                detail="No run_id from run_executes scenario",
                score=0,
            )
        resp = client.get(
            f"{base_url}/api/uar/runs/{run_id}/confidence",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            score = data.get("confidence", {}).get("score", 0)
            tier = data.get("confidence", {}).get("tier", "unknown")
            return BurnInEvidence(
                scenario="replay_confidence",
                passed=tier in ("Verified", "High", "Medium"),
                detail=f"Confidence {tier} (score={score})",
                score=score,
            )
        return BurnInEvidence(
            scenario="replay_confidence",
            passed=False,
            detail=(
                f"GET /api/uar/runs/{run_id}/confidence "
                f"→ {resp.status_code}"
            ),
            score=0,
        )
    except Exception as exc:
        return BurnInEvidence(
            scenario="replay_confidence",
            passed=False,
            detail=f"HTTP error: {exc}",
            score=0,
        )


SMOKE_SCENARIOS_DIRECT: list[ScenarioFn] = [
    _scenario_api_reachable_direct,
    _scenario_store_round_trip_direct,
    _scenario_replay_confidence_direct,
]

SMOKE_SCENARIOS_HTTP: list[ScenarioFn] = [
    _scenario_api_reachable_http,
    _scenario_store_round_trip_http,
    _scenario_replay_confidence_http,
]

__all__ = [
    "SMOKE_SCENARIOS_DIRECT",
    "SMOKE_SCENARIOS_HTTP",
    "ScenarioFn",
]
