"""Machine learning tools: Optuna hyperparameter tuning and ChromaDB store."""

from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.safe_eval import safe_eval
from uar.core.skill_utils import require_package, skill_guard


@register_skill("optuna_tune")
@skill_guard("Optuna tune")
def optuna_tune(ctx: PipelineContext) -> Dict[str, Any]:
    """Hyperparameter optimization with Optuna.

    Metadata:
        optuna_objective:
            Python expression for objective using 'trial' (Optuna trial)
        optuna_direction: 'minimize' or 'maximize'
        optuna_n_trials:  number of trials (default 20)
        optuna_params:    dict of parameter search spaces
                          e.g. {"x": {"type": "float", "low": -10, "high": 10}}
    """
    err = require_package("optuna")
    if err:
        return err

    import optuna
    import numpy as np

    meta = ctx.goal.metadata or {}
    direction = meta.get("optuna_direction", "minimize")
    n_trials = int(meta.get("optuna_n_trials", 20))
    params_def = meta.get(
        "optuna_params",
        {"x": {"type": "float", "low": -10, "high": 10}},
    )

    def objective(trial):
        # Build kwargs from params definition
        kwargs = {}
        for name, spec in params_def.items():
            t = spec.get("type", "float")
            if t == "float":
                kwargs[name] = trial.suggest_float(
                    name, spec["low"], spec["high"]
                )
            elif t == "int":
                kwargs[name] = trial.suggest_int(
                    name, spec["low"], spec["high"]
                )
            elif t == "categorical":
                kwargs[name] = trial.suggest_categorical(name, spec["choices"])

        # User provides the expression
        expr = meta.get("optuna_objective", "x**2")
        return safe_eval(expr, {"np": np, **kwargs})

    study = optuna.create_study(direction=direction)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_trial
    return {
        "status": "completed",
        "best_value": float(best.value),
        "best_params": best.params,
        "n_trials": n_trials,
        "direction": direction,
    }


@register_skill("chromadb_store")
@skill_guard("ChromaDB store", status="failed")
def chromadb_store(ctx: PipelineContext) -> Dict[str, Any]:
    """ChromaDB vector store operations.

    Metadata:
        chroma_operation: 'add', 'query', 'delete', 'peek'
        chroma_collection:  collection name (default 'default')
        chroma_documents:   list of document strings (for add)
        chroma_ids:         list of IDs (for add)
        chroma_metadatas:   list of metadata dicts (for add, optional)
        chroma_query:       query text (for query)
        chroma_n_results:   number of results (for query, default 5)
    """
    err = require_package("chromadb")
    if err:
        return err

    import chromadb
    from chromadb.config import Settings

    meta = ctx.goal.metadata or {}
    operation = meta.get("chroma_operation", "query")
    collection_name = meta.get("chroma_collection", "default")

    client = chromadb.Client(Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(collection_name)

    if operation == "add":
        docs = meta.get("chroma_documents", [])
        ids = meta.get("chroma_ids")
        metas = meta.get("chroma_metadatas")
        if not ids:
            ids = [f"doc_{i}" for i in range(len(docs))]
        collection.add(documents=docs, ids=ids, metadatas=metas)
        return {
            "status": "completed",
            "added": len(docs),
            "collection": collection_name,
        }

    elif operation == "query":
        query = meta.get("chroma_query", "")
        n = int(meta.get("chroma_n_results", 5))
        results = collection.query(query_texts=[query], n_results=n)
        return {
            "status": "completed",
            "query": query,
            "results": {
                "documents": results.get("documents", []),
                "distances": results.get("distances", []),
                "ids": results.get("ids", []),
            },
        }

    elif operation == "peek":
        results = collection.peek()
        return {
            "status": "completed",
            "count": len(results.get("ids", [])),
            "preview": results,
        }

    elif operation == "delete":
        ids = meta.get("chroma_ids", [])
        collection.delete(ids=ids)
        return {
            "status": "completed",
            "deleted": len(ids),
            "collection": collection_name,
        }

    else:
        return {
            "status": "failed",
            "error": "Unknown operation",
        }


@register_skill("flaml_auto")
@skill_guard("Flaml Auto")
def flaml_auto(ctx: PipelineContext) -> Dict[str, Any]:
    """Automated machine learning with FLAML.

    Metadata:
        flaml_task:       'classification' or 'regression'
        flaml_time_budget: time budget in seconds (default 30)
        flaml_metric:     optimization metric (default 'auto')
        flaml_data_path:  path to CSV file (optional, uses synthetic if
                          absent)
    """
    err = require_package("flaml")
    if err:
        return err

    from flaml import AutoML
    import pandas as pd

    meta = ctx.goal.metadata or {}
    task = meta.get("flaml_task", "classification")
    time_budget = float(meta.get("flaml_time_budget", 30))
    metric = meta.get("flaml_metric")
    data_path = meta.get("flaml_data_path")

    if data_path:
        df = pd.read_csv(data_path)
    else:
        from sklearn.datasets import make_classification, make_regression
        from sklearn.model_selection import train_test_split

        if task == "classification":
            X, y = make_classification(n_samples=500, n_features=10)
        else:
            X, y = make_regression(n_samples=500, n_features=10)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2
        )
        df = None

    try:
        automl = AutoML()
        fit_kwargs = {
            "X_train": X_train if df is None else df.drop(columns=["target"]),
            "y_train": y_train if df is None else df["target"],
            "task": task,
            "time_budget": time_budget,
            "metric": metric,
            "verbose": 0,
        }
        # Remove None values
        fit_kwargs = {k: v for k, v in fit_kwargs.items() if v is not None}
        automl.fit(**fit_kwargs)

        return {
            "status": "completed",
            "best_estimator": str(automl.best_estimator),
            "best_config": automl.best_config,
            "best_loss": float(automl.best_loss),
            "task": task,
            "time_budget": time_budget,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


@register_skill("pycaret_ml")
@skill_guard("Pycaret Ml")
def pycaret_ml(ctx: PipelineContext) -> Dict[str, Any]:
    """Automated ML pipeline with PyCaret.

    Metadata:
        pycaret_task:   'classification' or 'regression'
        pycaret_data_path: path to CSV file (uses synthetic if absent)
        pycaret_target: target column name (default 'target')
        pycaret_compare: run compare_models (default True)
        pycaret_model:  model ID to create when compare is False
    """
    err = require_package("pycaret")
    if err:
        return err

    import pandas as pd
    from sklearn.datasets import make_classification, make_regression

    meta = ctx.goal.metadata or {}
    task = meta.get("pycaret_task", "classification")
    data_path = meta.get("pycaret_data_path")
    target = meta.get("pycaret_target", "target")
    compare = meta.get("pycaret_compare", True)
    model_id = meta.get("pycaret_model", "lr")

    if data_path:
        df = pd.read_csv(data_path)
    else:
        if task == "classification":
            X, y = make_classification(n_samples=500, n_features=10)
        else:
            X, y = make_regression(n_samples=500, n_features=10)
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df[target] = y

    try:
        if task == "classification":
            from pycaret.classification import (
                setup, compare_models, create_model,
            )
        else:
            from pycaret.regression import (
                setup, compare_models, create_model,
            )

        setup(data=df, target=target, verbose=False, session_id=42)

        if compare:
            best = compare_models(verbose=False)
            model_info = str(best)
        else:
            model = create_model(model_id, verbose=False)
            model_info = str(model)

        return {
            "status": "completed",
            "task": task,
            "target": target,
            "best_model": model_info,
            "compare": compare,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


@register_skill("autogluon_ml")
@skill_guard("Autogluon Ml")
def autogluon_ml(ctx: PipelineContext) -> Dict[str, Any]:
    """Automated machine learning with AutoGluon.

    Metadata:
        autogluon_task:     'classification' or 'regression'
        autogluon_data_path: path to CSV (uses synthetic if absent)
        autogluon_target: target column (default 'target')
        autogluon_time_limit: training time limit in seconds (default 60)
        autogluon_preset: model preset (default 'medium_quality')
    """
    err = require_package("autogluon")
    if err:
        return err

    import pandas as pd
    from sklearn.datasets import make_classification, make_regression
    from sklearn.model_selection import train_test_split

    meta = ctx.goal.metadata or {}
    task = meta.get("autogluon_task", "classification")
    data_path = meta.get("autogluon_data_path")
    target = meta.get("autogluon_target", "target")
    time_limit = int(meta.get("autogluon_time_limit", 60))
    preset = meta.get("autogluon_preset", "medium_quality")

    if data_path:
        df = pd.read_csv(data_path)
    else:
        if task == "classification":
            X, y = make_classification(n_samples=500, n_features=10)
        else:
            X, y = make_regression(n_samples=500, n_features=10)
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df[target] = y

    train_df, test_df = train_test_split(df, test_size=0.2)

    try:
        from autogluon.tabular import TabularPredictor

        predictor = TabularPredictor(
            label=target,
            problem_type=task,
        ).fit(
            train_data=train_df,
            time_limit=time_limit,
            presets=preset,
        )

        leaderboard = predictor.leaderboard(test_df, silent=True)
        best_model = predictor.model_best
        score = predictor.evaluate(test_df)

        return {
            "status": "completed",
            "task": task,
            "target": target,
            "best_model": best_model,
            "leaderboard": leaderboard.to_dict()
            if hasattr(leaderboard, "to_dict")
            else str(leaderboard),
            "test_score": score,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
