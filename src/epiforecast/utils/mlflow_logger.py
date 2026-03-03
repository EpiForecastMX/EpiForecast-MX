"""Optional MLflow logging wrapper (no-op when mlflow is not installed)."""

from __future__ import annotations

from typing import Any

from loguru import logger as _logger

try:
    import mlflow

    _HAS_MLFLOW = True
except ImportError:
    _HAS_MLFLOW = False
    _logger.debug("MLflow no instalado: experiment tracking desactivado")


def log_training_run(
    model_name: str,
    entity: str | None,
    disease: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
    elapsed: float,
) -> None:
    """Log a single model training run to MLflow.

    Does nothing if mlflow is not installed.
    """
    if not _HAS_MLFLOW:
        return
    entity_tag = entity or "Nacional"
    run_name = f"{model_name}_{disease}_{entity_tag}"
    with mlflow.start_run(run_name=run_name, nested=True):
        safe_params = {k: str(v)[:250] for k, v in params.items()}
        mlflow.log_params(safe_params)
        safe_metrics = {k: float(v) for k, v in metrics.items() if isinstance(v, int | float)}
        mlflow.log_metrics(safe_metrics)
        mlflow.log_metric("elapsed_seconds", elapsed)


def log_prediction_run(
    model_name: str,
    disease: str,
    n_models: int,
    elapsed: float,
) -> None:
    """Log a prediction batch run to MLflow.

    Does nothing if mlflow is not installed.
    """
    if not _HAS_MLFLOW:
        return
    run_name = f"predict_{model_name}_{disease}"
    with mlflow.start_run(run_name=run_name, nested=True):
        mlflow.log_params({"model": model_name, "disease": disease})
        mlflow.log_metric("n_models_predicted", n_models)
        mlflow.log_metric("elapsed_seconds", elapsed)
