"""Tests for data_engineering skills error paths."""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.data_engineering import (
    airflow_dag,
    dbt_transform,
    spark_process,
    snowflake_etl,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestAirflowDagMissingPackage:
    """airflow_dag when airflow not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = airflow_dag(_ctx({"dag_file_path": "/tmp/dag.py"}))
        assert result["status"] == "failed"


class TestDbtTransformMissingPackage:
    """dbt_transform when dbt not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = dbt_transform(_ctx({"dbt_project_path": "."}))
        assert result["status"] == "failed"


class TestSparkProcessMissingPackage:
    """spark_process when pyspark not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = spark_process(_ctx({"spark_data_path": "/tmp/data.csv"}))
        assert result["status"] == "failed"

    def test_missing_data_path(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"pyspark": None}):
                result = spark_process(_ctx({}))
        assert result["status"] == "error"


class TestSnowflakeEtlMissingPackage:
    """snowflake_etl when connector not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = snowflake_etl(_ctx({"sf_account": "x"}))
        assert result["status"] == "failed"

    def test_missing_connection_params(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"snowflake": None}):
                result = snowflake_etl(_ctx({}))
        assert result["status"] == "error"
