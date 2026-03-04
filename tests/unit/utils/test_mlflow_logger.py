"""Tests for MLflow logger wrapper (no-op path)."""

from __future__ import annotations

from unittest.mock import patch

from epiforecast.utils.mlflow_logger import log_prediction_run, log_training_run


class TestLogTrainingRun:
    def test_noop_without_mlflow(self) -> None:
        with patch("epiforecast.utils.mlflow_logger._HAS_MLFLOW", False):
            # Should not raise
            log_training_run(
                model_name="prophet",
                entity="Nacional",
                disease="Depresion",
                params={"lr": 0.01},
                metrics={"rmse": 1.5, "mae": 1.0},
                elapsed=10.0,
            )

    def test_noop_with_none_entity(self) -> None:
        with patch("epiforecast.utils.mlflow_logger._HAS_MLFLOW", False):
            log_training_run(
                model_name="deepar",
                entity=None,
                disease="Parkinson",
                params={},
                metrics={},
                elapsed=5.0,
            )


class TestLogPredictionRun:
    def test_noop_without_mlflow(self) -> None:
        with patch("epiforecast.utils.mlflow_logger._HAS_MLFLOW", False):
            log_prediction_run(
                model_name="ensemble",
                disease="Alzheimer",
                n_models=333,
                elapsed=60.0,
            )
