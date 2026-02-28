# src/epiforecast/models/deepar/cross_validator.py
"""DeepAR cross-validator with temporal folds (SRP: CV only).

Uses TimeSeriesSplit for temporal cross-validation.
Trains with reduced epochs per fold for speed.
Computes RMSE, MAE, MAPE, MASE (same metrics as Prophet CV).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from epiforecast.constants import RANDOM_SEED
from epiforecast.utils.config import conf, logger

if TYPE_CHECKING:
    from epiforecast.models.deepar.model import DeepARForecaster


class DeepARCrossValidator:
    """Temporal cross-validator for DeepAR models.

    Evaluates forecast quality across multiple folds using
    reduced training epochs for speed.
    """

    def __init__(self, forecaster: DeepARForecaster, config: dict | None = None):
        _conf = config if config is not None else conf
        self.forecaster = forecaster
        self.n_splits: int = _conf.get("TS_SPLITS", 4)
        self.test_size: int = _conf.get("TEST_SIZE", 53)

        # Reduced epochs for CV folds (at least 25 for convergence)
        full_epochs = forecaster.epochs
        self.cv_epochs: int = max(25, full_epochs // 4)

    def run(self) -> dict[str, Any]:
        """Run temporal CV across all folds and return averaged metrics."""
        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=self.test_size)
        train_data = self.forecaster.train_data

        if train_data.empty or len(train_data) < self.test_size + 52:
            logger.warning("Datos insuficientes para CV DeepAR ({} filas)", len(train_data))
            return {"rmse": None, "mae": None, "mape": None, "smape": None, "mase": None}

        rmse_folds: list[float] = []
        mae_folds: list[float] = []
        mape_folds: list[float] = []
        smape_folds: list[float] = []
        mase_folds: list[float | None] = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_data)):
            train_fold = train_data.iloc[train_idx]
            val_fold = train_data.iloc[val_idx]

            logger.debug(
                "DeepAR CV Fold {}/{}: Train {} → {}, Val {} → {}",
                fold_idx + 1,
                self.n_splits,
                train_fold["ds"].min().date(),
                train_fold["ds"].max().date(),
                val_fold["ds"].min().date(),
                val_fold["ds"].max().date(),
            )

            try:
                metrics = self._evaluate_fold(train_fold, val_fold)
                rmse_folds.append(metrics["rmse"])
                mae_folds.append(metrics["mae"])
                mape_folds.append(metrics["mape"])
                smape_folds.append(metrics["smape"])
                mase_folds.append(metrics["mase"])

                logger.debug(
                    "Fold {}: RMSE={:.4f} MAE={:.4f} MAPE={:.2f}%",
                    fold_idx + 1,
                    metrics["rmse"],
                    metrics["mae"],
                    metrics["mape"],
                )
            except Exception as e:
                logger.warning("Error en fold {}: {}", fold_idx + 1, e)

        if not rmse_folds:
            return {"rmse": None, "mae": None, "mape": None, "smape": None, "mase": None}

        # Average metrics across folds
        valid_mase = [m for m in mase_folds if m is not None]
        result: dict[str, Any] = {
            "rmse": float(np.mean(rmse_folds)),
            "mae": float(np.mean(mae_folds)),
            "mape": float(np.mean(mape_folds)),
            "smape": float(np.mean(smape_folds)),
            "mase": float(np.mean(valid_mase)) if valid_mase else None,
        }

        logger.info(
            "DeepAR CV final: RMSE={:.4f} MAE={:.4f} MAPE={:.2f}% SMAPE={:.2f}%{}",
            result["rmse"],
            result["mae"],
            result["mape"],
            result["smape"],
            f" MASE={result['mase']:.3f}" if result["mase"] is not None else " MASE=N/A",
        )

        return result

    def _evaluate_fold(
        self,
        train_fold: pd.DataFrame,
        val_fold: pd.DataFrame,
    ) -> dict[str, Any]:
        """Train DeepAR on a fold and compute metrics against validation set."""
        import torch

        # Fix seeds
        torch.manual_seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        # Build dataset from train fold
        dataset = self.forecaster._build_dataset(train_fold)

        # Create estimator with reduced epochs (no early stopping in CV)
        estimator = self.forecaster._create_estimator(
            epochs=self.cv_epochs,
            prediction_length=len(val_fold),
            early_stopping=False,
        )
        predictor = estimator.train(dataset)

        # Generate forecasts
        forecasts = list(predictor.predict(dataset, num_samples=self.forecaster.num_samples))
        fc = forecasts[0]
        yhat = fc.mean[: len(val_fold)]

        y_true = val_fold["y"].to_numpy()[: len(yhat)]

        # Compute metrics
        from epiforecast.evaluation.metrics import smape as _smape

        rmse = float(np.sqrt(mean_squared_error(y_true, yhat)))
        mae = float(mean_absolute_error(y_true, yhat))
        mape = min(
            float(mean_absolute_percentage_error(y_true, yhat) * 100),
            999.0,
        )
        smape = _smape(y_true, yhat)

        # MASE: naive seasonal baseline (lag-52)
        y_train: np.ndarray = train_fold["y"].to_numpy()
        if len(y_train) > 52:
            mae_naive = float(np.mean(np.abs(y_train[52:] - y_train[:-52])))
            mase: float | None = mae / mae_naive if mae_naive > 0 else None
        else:
            mase = None

        return {"rmse": rmse, "mae": mae, "mape": mape, "smape": smape, "mase": mase}
