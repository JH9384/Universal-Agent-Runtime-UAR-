"""Tests for data_engineering remaining coverage gaps."""

import types
from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestAirflowDagRemaining:
    def test_missing_package(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "error"},
        ):
            from uar.skills.data_engineering import airflow_dag
            result = airflow_dag(_ctx({"dag_file_path": "/f"}))
        assert result["status"] == "error"

    def test_both_airflow_packages_missing(self):
        call_count = 0

        def _require(pkg):
            nonlocal call_count
            call_count += 1
            return {"status": "error", "missing": pkg}

        with patch(
            "uar.skills.data_engineering.require_package",
            side_effect=_require,
        ):
            from uar.skills.data_engineering import airflow_dag
            result = airflow_dag(_ctx({"dag_file_path": "/f"}))
        assert result["status"] == "error"
        assert call_count == 2

    def test_airflow_fallback_package_found(self):
        """First package missing, fallback package found."""
        def _require(pkg):
            if pkg == "airflow":
                return {"status": "error"}
            return None

        with patch(
            "uar.skills.data_engineering.require_package",
            side_effect=_require,
        ):
            with patch(
                "uar.skills.data_engineering.Path.exists", return_value=True
            ), patch(
                "uar.skills.data_engineering.Path.read_text",
                return_value="dag = 1",
            ):
                from uar.skills.data_engineering import airflow_dag
                result = airflow_dag(
                    _ctx({
                        "dag_file_path": "/fake/dag.py",
                        "dag_operation": "validate",
                    })
                )
        assert result["status"] == "completed"

    def test_list_tasks(self):
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="dag = 1",
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                with patch("importlib.util") as mock_util:
                    mock_spec = MagicMock()
                    mock_spec.loader = MagicMock()
                    mock_mod = types.ModuleType("dag")
                    mock_mod.dag = MagicMock()
                    mock_mod.dag.tasks = [MagicMock(task_id="t1")]
                    mock_util.spec_from_file_location.return_value = mock_spec
                    mock_util.module_from_spec.return_value = mock_mod
                    from uar.skills.data_engineering import airflow_dag
                    result = airflow_dag(
                        _ctx({
                            "dag_file_path": "/fake/dag.py",
                            "dag_operation": "list_tasks",
                        })
                    )
        assert result["status"] == "completed"

    def test_attribute_dag_call(self):
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="dag = airflow.DAG('test')",
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import airflow_dag
                result = airflow_dag(
                    _ctx({
                        "dag_file_path": "/fake/dag.py",
                        "dag_operation": "validate",
                    })
                )
        assert result["status"] == "completed"
        assert result["dag_instances"] == 1

    def test_list_tasks_no_tasks_attr(self):
        """Module has no object with .tasks attribute."""
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="dag = 1",
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                with patch("importlib.util") as mock_util:
                    mock_spec = MagicMock()
                    mock_spec.loader = MagicMock()
                    mock_mod = types.ModuleType("dag")
                    # No object with .tasks attribute
                    mock_util.spec_from_file_location.return_value = mock_spec
                    mock_util.module_from_spec.return_value = mock_mod
                    from uar.skills.data_engineering import airflow_dag
                    result = airflow_dag(
                        _ctx({
                            "dag_file_path": "/fake/dag.py",
                            "dag_operation": "list_tasks",
                        })
                    )
        assert result["status"] == "completed"
        assert result["tasks"] == []

    def test_list_tasks_spec_none(self):
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="dag = 1",
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                with patch("importlib.util") as mock_util:
                    mock_util.spec_from_file_location.return_value = None
                    from uar.skills.data_engineering import airflow_dag
                    result = airflow_dag(
                        _ctx({
                            "dag_file_path": "/fake/dag.py",
                            "dag_operation": "list_tasks",
                        })
                    )
        assert result["status"] == "failed"

    def test_unknown_operation(self):
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="dag = 1",
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import airflow_dag
                result = airflow_dag(
                    _ctx({
                        "dag_file_path": "/fake/dag.py",
                        "dag_operation": "bad",
                    })
                )
        assert result["status"] == "failed"

    def test_general_exception(self):
        with patch(
            "uar.skills.data_engineering.Path.exists", return_value=True
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            side_effect=RuntimeError("boom"),
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import airflow_dag
                result = airflow_dag(
                    _ctx({
                        "dag_file_path": "/fake/dag.py",
                        "dag_operation": "validate",
                    })
                )
        assert result["status"] == "error"


class TestDbtTransformRemaining:
    def test_missing_package(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "error"},
        ):
            from uar.skills.data_engineering import dbt_transform
            result = dbt_transform(_ctx({"dbt_project_path": "/f"}))
        assert result["status"] == "error"

    def test_both_dbt_packages_missing(self):
        call_count = 0

        def _require(pkg):
            nonlocal call_count
            call_count += 1
            return {"status": "error", "missing": pkg}

        with patch(
            "uar.skills.data_engineering.require_package",
            side_effect=_require,
        ):
            from uar.skills.data_engineering import dbt_transform
            result = dbt_transform(_ctx({"dbt_project_path": "/f"}))
        assert result["status"] == "error"
        assert call_count == 2

    def test_dbt_fallback_package_found(self):
        def _require(pkg):
            if pkg == "dbt":
                return {"status": "error"}
            return None

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        with patch(
            "uar.skills.data_engineering.subprocess.run",
            return_value=mock_proc,
        ), patch(
            "uar.skills.data_engineering.Path.exists", return_value=False,
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                side_effect=_require,
            ):
                from uar.skills.data_engineering import dbt_transform
                result = dbt_transform(_ctx({"dbt_project_path": "/f"}))
        assert result["status"] == "completed"

    def test_no_manifest(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        with patch(
            "uar.skills.data_engineering.subprocess.run",
            return_value=mock_proc,
        ), patch(
            "uar.skills.data_engineering.Path.exists",
            return_value=False,
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import dbt_transform
                result = dbt_transform(_ctx({"dbt_project_path": "/f"}))
        assert result["status"] == "completed"
        assert result["model_count"] == 0

    def test_with_models_and_no_target(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        manifest = (
            '{"nodes": {"model.a": {"resource_type": "model", '
            '"name": "a"}}}'
        )
        with patch(
            "uar.skills.data_engineering.subprocess.run",
            return_value=mock_proc,
        ), patch(
            "uar.skills.data_engineering.Path.exists",
            return_value=True,
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value=manifest,
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import dbt_transform
                result = dbt_transform(
                    _ctx({
                        "dbt_project_path": "/f",
                        "dbt_target": "",
                        "dbt_models": ["a"],
                    })
                )
        assert result["status"] == "completed"

    def test_exception(self):
        with patch(
            "uar.skills.data_engineering.subprocess.run",
            side_effect=RuntimeError("boom"),
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import dbt_transform
                result = dbt_transform(_ctx({"dbt_project_path": "/f"}))
        assert result["status"] == "error"


class TestSparkProcessRemaining:
    def test_missing_package(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "error"},
        ):
            from uar.skills.data_engineering import spark_process
            result = spark_process(_ctx({"spark_data_path": "/f"}))
        assert result["status"] == "error"

    def test_missing_data_path(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            from uar.skills.data_engineering import spark_process
            result = spark_process(_ctx({}))
        assert result["status"] == "failed"

    def test_parquet_format(self):
        mock_schema = MagicMock()
        mock_schema.fields = []
        mock_df = MagicMock()
        mock_df.schema = mock_schema
        mock_df.count.return_value = 10
        mock_df.limit.return_value.collect.return_value = []
        mock_spark = MagicMock()
        chain = mock_spark.read.format.return_value
        chain.load.return_value = mock_df
        mock_session = MagicMock()
        mock_session.builder.appName.return_value.getOrCreate.return_value = (
            mock_spark
        )
        mock_sql_mod = MagicMock()
        mock_sql_mod.SparkSession = mock_session
        with patch.dict("sys.modules", {
            "pyspark": MagicMock(),
            "pyspark.sql": mock_sql_mod,
        }):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import spark_process
                result = spark_process(
                    _ctx({
                        "spark_data_path": "/f",
                        "spark_format": "parquet",
                        "spark_options": {"mergeSchema": "true"},
                    })
                )
        assert result["status"] == "completed"
        assert result["format"] == "parquet"

    def test_exception(self):
        with patch.dict("sys.modules", {
            "pyspark": MagicMock(),
            "pyspark.sql": MagicMock(),
        }):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                mock_session = MagicMock()
                mock_session.builder.appName.return_value.getOrCreate.side_effect = RuntimeError("boom")  # noqa: E501
                import sys
                sys.modules["pyspark.sql"].SparkSession = mock_session
                from uar.skills.data_engineering import spark_process
                result = spark_process(
                    _ctx({"spark_data_path": "/f"})
                )
        assert result["status"] == "error"


class TestSnowflakeEtlRemaining:
    def test_missing_package(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value={"status": "error"},
        ):
            from uar.skills.data_engineering import snowflake_etl
            result = snowflake_etl(_ctx({"sf_query": "SELECT 1"}))
        assert result["status"] == "error"

    def test_both_snowflake_packages_missing(self):
        call_count = 0

        def _require(pkg):
            nonlocal call_count
            call_count += 1
            return {"status": "error", "missing": pkg}

        with patch(
            "uar.skills.data_engineering.require_package",
            side_effect=_require,
        ):
            from uar.skills.data_engineering import snowflake_etl
            result = snowflake_etl(_ctx({"sf_query": "SELECT 1"}))
        assert result["status"] == "error"
        assert call_count == 2

    def test_snowflake_fallback_package_found(self):
        def _require(pkg):
            if pkg == "snowflake":
                return {"status": "error"}
            return None

        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connector = MagicMock()
        mock_connector.connect.return_value = mock_conn
        mock_snowflake = MagicMock()
        mock_snowflake.connector = mock_connector
        with patch.dict("sys.modules", {
            "snowflake": mock_snowflake,
            "snowflake.connector": mock_connector,
        }):
            with patch(
                "uar.skills.data_engineering.require_package",
                side_effect=_require,
            ):
                from uar.skills.data_engineering import snowflake_etl
                result = snowflake_etl(
                    _ctx({
                        "sf_account": "a",
                        "sf_user": "u",
                        "sf_password": "p",
                        "sf_database": "d",
                        "sf_query": "INSERT INTO t VALUES (1)",
                    })
                )
        assert result["status"] == "completed"

    def test_missing_params(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            from uar.skills.data_engineering import snowflake_etl
            result = snowflake_etl(_ctx({"sf_query": "SELECT 1"}))
        assert result["status"] == "failed"

    def test_no_description(self):
        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connector = MagicMock()
        mock_connector.connect.return_value = mock_conn
        mock_snowflake = MagicMock()
        mock_snowflake.connector = mock_connector
        with patch.dict("sys.modules", {
            "snowflake": mock_snowflake,
            "snowflake.connector": mock_connector,
        }):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import snowflake_etl
                result = snowflake_etl(
                    _ctx({
                        "sf_account": "a",
                        "sf_user": "u",
                        "sf_password": "p",
                        "sf_database": "d",
                        "sf_query": "INSERT INTO t VALUES (1)",
                    })
                )
        assert result["status"] == "completed"
        assert result["results"] == []

    def test_exception(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            mock_connector = MagicMock()
            mock_connector.connect.side_effect = RuntimeError("conn failed")
            mock_snowflake = MagicMock()
            mock_snowflake.connector = mock_connector
            with patch.dict("sys.modules", {
                "snowflake": mock_snowflake,
                "snowflake.connector": mock_connector,
            }):
                from uar.skills.data_engineering import snowflake_etl
                result = snowflake_etl(
                    _ctx({
                        "sf_account": "a",
                        "sf_user": "u",
                        "sf_password": "p",
                        "sf_database": "d",
                        "sf_query": "SELECT 1",
                    })
                )
        assert result["status"] == "error"
