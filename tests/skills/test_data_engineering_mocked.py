"""Tests for data_engineering skills with mocked heavy deps."""

import types
from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestAirflowDagMocked:
    """airflow_dag with mocked file system."""

    def test_validate_valid_dag(self):
        dag_content = """
from airflow import DAG
from airflow.operators.python import PythonOperator

dag = DAG('test_dag', start_date=None)
def f(): pass
task = PythonOperator(task_id='t1', python_callable=f, dag=dag)
"""
        with patch(
            "uar.skills.data_engineering.Path.exists",
            return_value=True,
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value=dag_content,
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
        assert result["syntax_valid"] is True
        assert result["dag_instances"] >= 1

    def test_validate_syntax_error(self):
        with patch(
            "uar.skills.data_engineering.Path.exists",
            return_value=True,
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value="def broken(",
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
        assert result["syntax_valid"] is False

    def test_missing_dag_path(self):
        with patch(
            "uar.skills.data_engineering.require_package",
            return_value=None,
        ):
            from uar.skills.data_engineering import airflow_dag
            result = airflow_dag(_ctx({"dag_operation": "validate"}))
        assert result["status"] == "failed"


class TestDbtTransformMocked:
    """dbt_transform with mocked subprocess."""

    def test_compile(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Compiled 5 models"
        mock_proc.stderr = ""

        manifest_content = (
            '{"nodes": {"model.a": {"resource_type": "model", '
            '"name": "a"}, "seed.b": {"resource_type": "seed", '
            '"name": "b"}}}'
        )

        with patch(
            "uar.skills.data_engineering.subprocess.run",
            return_value=mock_proc,
        ), patch(
            "uar.skills.data_engineering.Path.exists",
            return_value=True,
        ), patch(
            "uar.skills.data_engineering.Path.read_text",
            return_value=manifest_content,
        ):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import dbt_transform
                result = dbt_transform(
                    _ctx({
                        "dbt_project_path": "/fake/proj",
                        "dbt_target": "dev",
                    })
                )
        assert result["status"] == "completed"
        assert result["model_count"] == 1
        assert "a" in result["models"]


class TestSparkProcessMocked:
    """spark_process with mocked pyspark."""

    def test_read_csv_and_sample(self):
        mock_schema = MagicMock()
        mock_field = MagicMock()
        mock_field.name = "col1"
        mock_field.dataType = "StringType"
        mock_schema.fields = [mock_field]

        mock_df = MagicMock()
        mock_df.schema = mock_schema
        mock_df.count.return_value = 100
        mock_row = MagicMock()
        mock_row.asDict.return_value = {"col1": "hello"}
        mock_df.limit.return_value.collect.return_value = [mock_row]

        mock_spark = MagicMock()
        chain = mock_spark.read.option.return_value
        chain = chain.option.return_value
        chain = chain.format.return_value
        chain.load.return_value = mock_df

        mock_session = MagicMock()
        mock_session.builder.appName.return_value.getOrCreate.return_value = mock_spark  # noqa: E501

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
                        "spark_data_path": "/fake/data.csv",
                        "spark_format": "csv",
                        "spark_sample_n": 3,
                    })
                )
        assert result["status"] == "completed"
        assert result["format"] == "csv"
        assert result["row_count"] == 100
        assert len(result["sample"]) == 1

    def test_with_sql(self):
        mock_schema = MagicMock()
        mock_schema.fields = []
        mock_df = MagicMock()
        mock_df.schema = mock_schema
        mock_df.count.return_value = 50
        mock_df.limit.return_value.collect.return_value = []
        mock_df.createOrReplaceTempView = MagicMock()

        mock_result_df = MagicMock()
        mock_result_df.limit.return_value.collect.return_value = []

        mock_spark = MagicMock()
        chain = mock_spark.read.option.return_value
        chain = chain.option.return_value
        chain = chain.format.return_value
        chain.load.return_value = mock_df
        mock_spark.sql.return_value = mock_result_df

        mock_session = MagicMock()
        mock_session.builder.appName.return_value.getOrCreate.return_value = mock_spark  # noqa: E501

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
                        "spark_data_path": "/fake/data.parquet",
                        "spark_format": "parquet",
                        "spark_sql": "SELECT * FROM data",
                    })
                )
        assert result["status"] == "completed"
        assert result["sql_applied"] is True


class TestSnowflakeEtlMocked:
    """snowflake_etl with mocked connector."""

    def test_execute_query(self):
        mock_cursor = MagicMock()
        mock_cursor.description = [["ID"], ["NAME"]]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        mock_cursor.rowcount = 2

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_snowflake = types.ModuleType("snowflake")
        mock_snowflake.connector = MagicMock()
        mock_snowflake.connector.connect = MagicMock(return_value=mock_conn)

        with patch.dict("sys.modules", {
            "snowflake": mock_snowflake,
            "snowflake.connector": mock_snowflake.connector,
        }):
            with patch(
                "uar.skills.data_engineering.require_package",
                return_value=None,
            ):
                from uar.skills.data_engineering import snowflake_etl
                result = snowflake_etl(
                    _ctx({
                        "sf_account": "myaccount",
                        "sf_user": "user",
                        "sf_password": "pass",
                        "sf_database": "db",
                        "sf_schema": "PUBLIC",
                        "sf_warehouse": "wh",
                        "sf_query": "SELECT * FROM t",
                    })
                )
        assert result["status"] == "completed"
        assert result["row_count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["ID"] == 1
