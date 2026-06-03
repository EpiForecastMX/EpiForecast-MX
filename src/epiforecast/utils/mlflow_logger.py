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
    # El tracking NUNCA debe tumbar el entrenamiento. Cada worker loky es un proceso
    # fresco sin run activo: ``nested=True`` ahí lanza MlflowException ("experiment 0 not
    # found") y joblib re-propaga, abortando todo el lote de 333 modelos. Por eso se fija
    # un experimento por padecimiento, se usa un run de nivel superior y se traga cualquier
    # fallo de tracking (disco, carrera entre workers, versión) como warning.
    try:
        mlflow.set_experiment(f"epiforecast_{disease}")
        with mlflow.start_run(run_name=run_name):
            safe_params = {k: str(v)[:250] for k, v in params.items()}
            mlflow.log_params(safe_params)
            safe_metrics = {k: float(v) for k, v in metrics.items() if isinstance(v, int | float)}
            mlflow.log_metrics(safe_metrics)
            mlflow.log_metric("elapsed_seconds", elapsed)
    except Exception as exc:  # noqa: BLE001 — tracking opcional, nunca fatal
        _logger.warning("MLflow log_training_run fallo (ignorado): {}", exc)


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
    try:
        mlflow.set_experiment(f"epiforecast_{disease}")
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({"model": model_name, "disease": disease})
            mlflow.log_metric("n_models_predicted", n_models)
            mlflow.log_metric("elapsed_seconds", elapsed)
    except Exception as exc:  # noqa: BLE001 — tracking opcional, nunca fatal
        _logger.warning("MLflow log_prediction_run fallo (ignorado): {}", exc)
