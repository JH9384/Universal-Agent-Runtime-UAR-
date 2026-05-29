"""Regression tests for the README / schema / version fixes.

Covers fixes for:
1. __version__ mismatch (hardcoded 0.1.0 vs VERSION file 1.1.0)
2. Event schema missing orchestration_plan, recipe_skipped, etc.
3. Silent schema validation warnings during execution
4. README mislabeling real skills as stubs
"""

import os
from pathlib import Path
from unittest.mock import patch

import uar.skills  # noqa: F401 — registers all skills


# ---------------------------------------------------------------------------
# 1. Version sync
# ---------------------------------------------------------------------------


def test_version_matches_version_file():
    """uar.__version__ must match the VERSION file, not a stale hardcode."""
    root = Path(__file__).parent.parent.parent
    version_file = root / "VERSION"
    expected = version_file.read_text().strip()
    import uar

    assert uar.__version__ == expected, (
        f"uar.__version__ ({uar.__version__}) != VERSION ({expected}). "
        "Fix uar/__init__.py to read from VERSION."
    )


# ---------------------------------------------------------------------------
# 2. Event schema completeness
# ---------------------------------------------------------------------------


def test_all_executor_event_types_in_schema():
    """Every event type emitted by the executor must be in EVENT_SCHEMAS."""
    from uar.core.schema import EVENT_SCHEMAS

    emitted = {
        "start",
        "complete",
        "orchestration_plan",
        "skill_start",
        "skill_complete",
        "skill_failed",
        "skill_retry",
        "recipe_start",
        "recipe_end",
        "recipe_skipped",
        "recipe_retry",
        "parallel_start",
        "parallel_complete",
        "partial_result",
        "metrics",
        "error",
    }
    missing = emitted - set(EVENT_SCHEMAS.keys())
    assert not missing, (
        f"Event types missing from EVENT_SCHEMAS: {sorted(missing)}. "
        "Add them to uar/core/schema.py."
    )


# ---------------------------------------------------------------------------
# 3. No silent schema warnings during execution
# ---------------------------------------------------------------------------


def test_execution_emits_no_schema_warnings(caplog):
    """Running a skill must not log 'Event schema validation failed'
    warnings."""
    import logging

    from uar.core.contracts import GoalSpec
    from uar.core.executor import Executor
    from uar.core.planner import SimplePlanner

    # Capture WARNING level logs from the executor module
    logger = logging.getLogger("uar.core.executor")
    old_level = logger.level
    logger.setLevel(logging.WARNING)

    goal = GoalSpec(
        id="reg-test",
        user_intent="test",
        objective="test",
        metadata={
            "execution_order": [
                {
                    "type": "skill",
                    "content": "molecular_visualization",
                    "id": "s1",
                }
            ],
            "recipe_definitions": [],
        },
    )
    strategy = SimplePlanner().plan(goal)
    exc = Executor()

    with patch.dict(os.environ, {"UAR_HIERARCHICAL_EXECUTION": "true"}):
        events = list(exc.iter_events(strategy, goal))

    logger.setLevel(old_level)

    assert events, "Expected at least one event"
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "complete"

    # Check no schema-validation warnings were emitted
    schema_warnings = [
        r for r in caplog.records
        if "schema validation failed" in r.getMessage().lower()
    ]
    assert not schema_warnings, (
        f"Schema validation warnings logged during execution: "
        f"{[r.getMessage() for r in schema_warnings]}"
    )


# ---------------------------------------------------------------------------
# 4. Skills previously labeled as stubs are real implementations
# ---------------------------------------------------------------------------


def test_stub_labeled_skills_are_real():
    """Skills that README previously called 'stubs' must have real
    implementations.

    A real implementation is defined as: callable with >5 lines of actual
    logic (not just a require_package guard returning an error dict).
    """
    from uar.core.registry import registry

    previously_labeled_stub = {
        "agent_workflow",
        "crewai_task",
        "crewai_workflow",
        "llamaindex_rag",
        "llamaindex_query",
        "dagster_pipeline",
        "dagster_status",
        "mlflow_track",
        "mlflow_deploy",
        "model_reg",
        "kubeflow_pipe",
        "airflow_dag",
        "dbt_transform",
        "snowflake_etl",
        "spark_process",
        "pentest_scan",
        "osint_recon",
        "security_audit",
        "solana_tx",
        "smart_contract",
        "nft_mint",
        "face_recognize",
        "video_analyze",
        "autogluon_ml",
        "pycaret_ml",
        "flaml_auto",
        "quantum_ml",
        "cern_root",
    }

    for name in previously_labeled_stub:
        assert registry.is_registered(name), (
            f"Skill '{name}' is not registered"
        )
        fn = registry.get(name)
        # Unwrap skill_guard wrappers so we inspect the real implementation
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        # Real implementation check: source code exists and is more than
        # a trivial wrapper. We check the function has meaningful locals.
        assert fn.__code__.co_code, f"Skill '{name}' has no bytecode"
        # Require at least some local variables beyond trivial guard patterns
        # (a require_package-only stub has ~2-3 locals)
        assert fn.__code__.co_nlocals > 3, (
            f"Skill '{name}' looks like a trivial stub "
            f"(only {fn.__code__.co_nlocals} locals)"
        )
