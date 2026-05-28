"""Stub skills for UI placeholder items without full implementations.

Each stub checks for its primary dependency and returns a helpful
message if unavailable. Install the required package to unlock full
functionality.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package


_STUBS: Dict[str, str] = {
    "airflow_dag": "apache-airflow",
    "auto_down": "autonomi",
    "auto_status": "autonomi",
    "auto_up": "autonomi",
    "autogluon_ml": "autogluon",
    "cern_root": "uproot",
    "crypto_analyze": "pycryptodome",
    "dbt_transform": "dbt-core",
    "deps": "",
    "eco_canon": "",
    "eco_foundation": "",
    "eco_status": "",
    "face_recognize": "face-recognition",
    "flaml_auto": "flaml",
    "gr_full": "graphrag",
    "gr_index": "graphrag",
    "gr_query": "graphrag",
    "kubeflow_pipe": "kfp",
    "mlflow_deploy": "mlflow",
    "mlflow_track": "mlflow",
    "model_reg": "mlflow",
    "nft_mint": "web3",
    "osint_recon": "shodan",
    "pentest_scan": "python-nmap",
    "pycaret_ml": "pycaret",
    "review": "",
    "security_audit": "bandit",
    "smart_contract": "web3",
    "snowflake_etl": "snowflake-connector-python",
    "solana_tx": "solana",
    "spark_process": "pyspark",
    "video_analyze": "moviepy",
}


def _make_stub(
    skill_name: str, package: str
) -> Callable[[PipelineContext], Dict[str, Any]]:
    """Factory for dependency-check stub skills."""

    def stub_skill(ctx: PipelineContext) -> Dict[str, Any]:
        if package:
            available = require_package(package) is None
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
