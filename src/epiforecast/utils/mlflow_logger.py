"""Optional MLflow logging wrapper (no-op when mlflow is not installed)."""

from __future__ import annotations

from typing import Any

try:
    import mlflow

    _HAS_MLFLOW = True
except ImportError:
    _HAS_MLFLOW = False


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
