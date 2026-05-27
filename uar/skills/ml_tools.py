"""Machine learning tools: Optuna hyperparameter tuning and ChromaDB store."""

import logging
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.safe_eval import safe_eval

logger = logging.getLogger(__name__)


@register_skill("optuna_tune")
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
    import importlib.util
    if importlib.util.find_spec("optuna") is None:
        return {
            "status": "failed",
            "error": "Optuna not installed. pip install optuna",
        }

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

    try:
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
    except Exception as exc:
        logger.warning(f"detect_trend failed: {exc}")
        return {"status": "failed", "error": "Trend detection failed"}


@register_skill("chromadb_store")
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
    import importlib.util
    if importlib.util.find_spec("chromadb") is None:
        return {
            "status": "failed",
            "error": "ChromaDB not installed. pip install chromadb",
        }

    import chromadb
    from chromadb.config import Settings

    meta = ctx.goal.metadata or {}
    operation = meta.get("chroma_operation", "query")
    collection_name = meta.get("chroma_collection", "default")

    try:
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
    except Exception as exc:
        logger.warning("chromadb_store failed: %s", exc)
        return {"status": "failed", "error": "ChromaDB operation failed"}
