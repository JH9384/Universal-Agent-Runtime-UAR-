"""Stub skills for UI placeholder items without full implementations.

Each stub checks for its primary dependency and returns a helpful
message if unavailable. Install the required package to unlock full
functionality.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Callable, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


_STUBS: Dict[str, str] = {
    "agent_workflow": "autogen",
    "airflow_dag": "apache-airflow",
    "auto_down": "autonomi",
    "auto_status": "autonomi",
    "auto_up": "autonomi",
    "autogluon_ml": "autogluon",
    "bio_compute": "biopython",
    "blackboard_status": "",
    "budget_status": "",
    "cern_root": "uproot",
    "chem_analysis": "rdkit",
    "chromadb_store": "chromadb",
    "crewai_task": "crewai",
    "crewai_workflow": "crewai",
    "crypto_analyze": "pycryptodome",
    "dagster_pipeline": "dagster",
    "dagster_status": "dagster",
    "dbt_transform": "dbt-core",
    "deps": "",
    "diff_eq_solve": "scipy",
    "eco_canon": "",
    "eco_foundation": "",
    "eco_status": "",
    "face_recognize": "face-recognition",
    "flaml_auto": "flaml",
    "gr_full": "graphrag",
    "gr_index": "graphrag",
    "gr_query": "graphrag",
    "guardrail_check": "",
    "kubeflow_pipe": "kfp",
    "llamaindex_query": "llama-index",
    "llamaindex_rag": "llama-index",
    "mlflow_deploy": "mlflow",
    "mlflow_track": "mlflow",
    "model_reg": "mlflow",
    "nft_mint": "web3",
    "opencv_process": "opencv-python",
    "optuna_tune": "optuna",
    "osint_recon": "shodan",
    "pentest_scan": "python-nmap",
    "pycaret_ml": "pycaret",
    "quantum_circuit": "qiskit",
    "quantum_ml": "pennylane",
    "relativity": "sympy",
    "review": "",
    "scipy_opt": "scipy",
    "security_audit": "bandit",
    "smart_contract": "web3",
    "snowflake_etl": "snowflake-connector-python",
    "solana_tx": "solana",
    "spark_process": "pyspark",
    "video_analyze": "moviepy",
    "yolo_detect": "ultralytics",
}


def _make_stub(
    skill_name: str, package: str
) -> Callable[[PipelineContext], Dict[str, Any]]:
    """Factory for dependency-check stub skills."""

    def stub_skill(ctx: PipelineContext) -> Dict[str, Any]:
        if package:
            available = importlib.util.find_spec(package) is not None
        else:
            available = True

        return {
            "status": "completed",
            "goal": ctx.goal.user_intent,
            "result": {
                "skill": skill_name,
                "package": package,
                "available": available,
                "message": (
                    f"{skill_name} stub: install '{package}' for "
                    f"full functionality"
                    if package and not available
                    else f"{skill_name} ready"
                ),
            },
            "metrics": {"available": available},
        }

    stub_skill.__name__ = skill_name
    stub_skill.__doc__ = (
        f"Stub skill for {skill_name}. "
        f"Dependency: {package or 'none'}."
    )
    return stub_skill


# Register all stub skills
for _name, _pkg in _STUBS.items():
    try:
        register_skill(_name)(_make_stub(_name, _pkg))
    except Exception:
        pass  # Already registered elsewhere
