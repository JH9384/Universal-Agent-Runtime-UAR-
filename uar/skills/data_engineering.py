"""Data engineering skills for UAR.

Implements Airflow DAG validation, dbt compilation, Spark processing,
and Snowflake ETL.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from uar.core.contracts import PipelineContext
from uar.core.registry import register_skill
from uar.core.skill_utils import require_package, skill_guard


@register_skill("airflow_dag")
@skill_guard("Airflow Dag")
def airflow_dag(ctx: PipelineContext) -> Dict[str, Any]:
    """Validate Airflow DAG files and return DAG structure.

    Metadata:
        dag_file_path:   path to the .py DAG file
        dag_operation:   'validate', 'list_tasks' (default 'validate')
    """
    err = require_package("airflow")
    if err:
        # Also accept apache-airflow package name
        err2 = require_package("apache-airflow")
        if err2:
            return err

    meta = ctx.goal.metadata or {}
    dag_path = meta.get("dag_file_path", "")
    operation = meta.get("dag_operation", "validate")

    if not dag_path:
        return {"status": "failed", "error": "dag_file_path required"}

    try:
        if operation == "validate":
            # Syntax-level validation via ast / import attempt
            import ast

            source = Path(dag_path).read_text()
            tree = ast.parse(source)
            dag_count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "DAG":
                        dag_count += 1
                    elif (
                        isinstance(func, ast.Attribute)
                        and func.attr == "DAG"
                    ):
                        dag_count += 1

            return {
                "status": "completed",
                "operation": operation,
                "dag_file": dag_path,
                "syntax_valid": True,
                "dag_instances": dag_count,
            }

        elif operation == "list_tasks":
            # Attempt to import and inspect the DAG module
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "dag_module", dag_path
            )
            if spec is None or spec.loader is None:
                return {
                    "status": "failed",
                    "error": "Could not load DAG module",
                }
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            tasks: List[str] = []
            for name in dir(mod):
                obj = getattr(mod, name)
                if hasattr(obj, "tasks"):
                    tasks = [t.task_id for t in getattr(obj, "tasks", [])]
                    break

            return {
                "status": "completed",
                "operation": operation,
                "dag_file": dag_path,
                "tasks": tasks,
                "task_count": len(tasks),
            }

        return {"status": "failed", "error": "Unknown operation"}
    except SyntaxError as exc:
        return {
            "status": "completed",
            "operation": operation,
            "dag_file": dag_path,
            "syntax_valid": False,
            "error": str(exc),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("dbt_transform")
@skill_guard("Dbt Transform")
def dbt_transform(ctx: PipelineContext) -> Dict[str, Any]:
    """Run dbt compile on a project and return model list.

    Metadata:
        dbt_project_path: path to dbt project directory (default '.')
        dbt_target:       target profile (default 'dev')
        dbt_models:       list of model selectors (optional)
    """
    err = require_package("dbt")
    if err:
        err2 = require_package("dbt-core")
        if err2:
            return err

    meta = ctx.goal.metadata or {}
    project_path = meta.get("dbt_project_path", ".")
    target = meta.get("dbt_target", "dev")
    models = meta.get("dbt_models", [])

    try:
        cmd = ["dbt", "compile", "--project-dir", project_path]
        if target:
            cmd.extend(["--target", target])
        if models:
            for m in models:
                cmd.extend(["--select", m])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )

        # Parse manifest.json for compiled models
        manifest_path = Path(project_path) / "target" / "manifest.json"
        models_list: List[str] = []
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            nodes = manifest.get("nodes", {})
            for key, node in nodes.items():
                if node.get("resource_type") == "model":
                    models_list.append(node.get("name", key))

        return {
            "status": "completed",
            "returncode": proc.returncode,
            "models": models_list,
            "model_count": len(models_list),
            "stdout_preview": proc.stdout[:2000] if proc.stdout else "",
            "stderr_preview": proc.stderr[:2000] if proc.stderr else "",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("spark_process")
@skill_guard("Spark Process")
def spark_process(ctx: PipelineContext) -> Dict[str, Any]:
    """Create Spark session, read data, run SQL, return schema + sample.

    Metadata:
        spark_data_path:  path to CSV or Parquet file
        spark_format:     'csv', 'parquet', 'json' (default 'csv')
        spark_sql:        SQL query to run (optional)
        spark_options:    dict of format options (e.g. header, inferSchema)
        spark_sample_n:   number of sample rows (default 5)
    """
    err = require_package("pyspark")
    if err:
        return err

    from pyspark.sql import SparkSession

    meta = ctx.goal.metadata or {}
    data_path = meta.get("spark_data_path", "")
    fmt = meta.get("spark_format", "csv")
    sql = meta.get("spark_sql", "")
    options = meta.get("spark_options", {})
    sample_n = int(meta.get("spark_sample_n", 5))

    if not data_path:
        return {"status": "failed", "error": "spark_data_path required"}

    try:
        spark = SparkSession.builder.appName(
            "UAR_Spark"
        ).getOrCreate()

        reader = spark.read
        if fmt == "csv":
            reader = reader.option("header", "true")
            reader = reader.option("inferSchema", "true")
        for k, v in options.items():
            reader = reader.option(k, v)
        df = reader.format(fmt).load(data_path)

        schema = [
            {"name": f.name, "type": str(f.dataType)}
            for f in df.schema.fields
        ]
        row_count = df.count()

        result_df = df
        if sql:
            df.createOrReplaceTempView("data")
            result_df = spark.sql(sql)

        sample = [
            row.asDict() for row in result_df.limit(sample_n).collect()
        ]

        return {
            "status": "completed",
            "format": fmt,
            "schema": schema,
            "row_count": row_count,
            "sample": sample,
            "sql_applied": bool(sql),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("snowflake_etl")
@skill_guard("Snowflake Etl")
def snowflake_etl(ctx: PipelineContext) -> Dict[str, Any]:
    """Connect to Snowflake, execute query, return results.

    Metadata:
        sf_account:   Snowflake account identifier
        sf_user:      username
        sf_password:  password (or uses env SF_PASSWORD)
        sf_database:  database name
        sf_schema:    schema name (default 'PUBLIC')
        sf_warehouse: warehouse name
        sf_query:     SQL query to execute
    """
    err = require_package("snowflake")
    if err:
        err2 = require_package("snowflake-connector-python")
        if err2:
            return err

    import os
    import snowflake.connector

    meta = ctx.goal.metadata or {}
    account = meta.get("sf_account", "")
    user = meta.get("sf_user", "")
    password = meta.get("sf_password", os.environ.get("SF_PASSWORD", ""))
    database = meta.get("sf_database", "")
    schema = meta.get("sf_schema", "PUBLIC")
    warehouse = meta.get("sf_warehouse", "")
    query = meta.get("sf_query", "")

    if not all([account, user, password, database, query]):
        return {
            "status": "failed",
            "error": (
                "Missing required connection params: "
                "account, user, password, database, query"
            ),
        }

    try:
        conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            database=database,
            schema=schema,
            warehouse=warehouse,
        )
        cursor = conn.cursor()
        cursor.execute(query)

        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [
                dict(zip(columns, row)) for row in rows[:1000]
            ]
            row_count = len(rows)
        else:
            results = []
            row_count = cursor.rowcount

        cursor.close()
        conn.close()

        return {
            "status": "completed",
            "row_count": row_count,
            "results": results,
            "query": query,
            "database": database,
            "schema": schema,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
