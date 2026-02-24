# src/epiforecast/models/prophet/cross_validator.py
"""Prophet cross-validator with weighted folds and Newton protection (SRP: CV only).

Features:
- Temporal cross-validation via TimeSeriesSplit
- Progressive fold weights (recent folds weighted higher)
- MASE metric (vs seasonal naive lag-52)
- Per-fold timeout to detect Newton optimizer fallback
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import TYPE_CHECKING

import numpy as np
from prophet import Prophet
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from src.epiforecast.utils.config import conf, logger

if TYPE_CHECKING:
    from src.epiforecast.models.prophet.model import ProphetForecaster


class ProphetCrossValidator:
    """Temporal cross-validator for Prophet models.

    Evaluates one HP combination across multiple folds with
    optional progressive weighting and Newton timeout protection.
    """

    def __init__(self, forecaster: ProphetForecaster):
        self.forecaster = forecaster
        self.n_splits: int = conf["TS_SPLITS"]
        self.test_size: int = conf["TEST_SIZE"]
        self.cv_weights: list[float] | None = conf.get("cv_weights", None)
        self.fold_timeout: int = conf.get("cv_timeout_por_fold", 0)

    def run(self) -> tuple[dict, dict]:
        """Run full CV by delegating to ProphetTuner.

        This is called from ProphetForecaster.cross_validate().
        """
        from src.epiforecast.models.prophet.tuner import ProphetTuner

        tuner = ProphetTuner(self.forecaster)
        return tuner.run()

    def evaluate_combo(
        self, params: dict,
    ) -> tuple[dict, bool, float | None]:
        """Evaluate a single HP combination across all CV folds.

        Args:
            params: HP dict (seasonality_mode, changepoint_prior_scale, etc.)

        Returns:
            (metrics_dict, timed_out, newton_cp_threshold)
            - metrics_dict: {rmse, mae, mape, mase} averaged across folds
            - timed_out: True if any fold hit Newton timeout
            - newton_cp_threshold: cp value that caused timeout (or None)
        """
        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=self.test_size)
        train_data = self.forecaster.train_data

        rmse_folds: list[float] = []
        mae_folds: list[float] = []
        mape_folds: list[float] = []
        mase_folds: list[float | None] = []
        fold_indices: list[int] = []

        timed_out = False
        newton_cp: float | None = None
        cp = params.get("changepoint_prior_scale", 0)

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_data)):
            train_fold = train_data.iloc[train_idx]
            val_fold = train_data.iloc[val_idx]

            logger.debug(
                "Fold {}: Train hasta {}, Val {} → {}",
                fold_idx + 1, train_fold["ds"].max().date(),
                val_fold["ds"].min().date(), val_fold["ds"].max().date(),
            )

            try:
                model = self.forecaster._create_prophet(**params)

                # Layer 2: per-fold timeout to detect Newton
                if self.fold_timeout:
                    fit_ok = self._fit_with_timeout(model, train_fold, self.fold_timeout)
                    if not fit_ok:
                        logger.warning(
                            "Timeout fold: >{:.0f}s en fold {}/{}. Newton → skip cp ≤ {}",
                            self.fold_timeout, fold_idx + 1, self.n_splits, cp,
                        )
                        timed_out = True
                        newton_cp = cp
                        break
                else:
                    model.fit(train_fold)

                # Predict and compute metrics
                forecast = model.predict(val_fold[["ds"]])
                merged = val_fold[["ds", "y"]].merge(forecast[["ds", "yhat"]], on="ds")

                rmse = float(np.sqrt(mean_squared_error(merged["y"], merged["yhat"])))
                mae = float(mean_absolute_error(merged["y"], merged["yhat"]))
                mape = min(
                    float(mean_absolute_percentage_error(merged["y"], merged["yhat"]) * 100),
                    999.0,
                )

                # MASE: MAE / MAE_naive_seasonal (lag-52 weeks)
                y_train = train_fold["y"].values
                if len(y_train) > 52:
                    mae_naive = float(np.mean(np.abs(y_train[52:] - y_train[:-52])))
                    mase = mae / mae_naive if mae_naive > 0 else None
                else:
                    mase = None

                rmse_folds.append(rmse)
                mae_folds.append(mae)
                mape_folds.append(mape)
                mase_folds.append(mase)
                fold_indices.append(fold_idx)

            except Exception as e:
                logger.warning("Excepción en fold {}: {}", fold_idx + 1, e)
                continue

        # Aggregate fold metrics
        if timed_out or not rmse_folds:
            return (
                {"rmse": float("inf"), "mae": float("inf"), "mape": float("inf"), "mase": None},
                timed_out,
                newton_cp,
            )

        metrics = self._aggregate_folds(
            rmse_folds, mae_folds, mape_folds, mase_folds, fold_indices,
        )

        logger.debug(
            "Métricas CV: RMSE={:.4f}, MAE={:.4f}, MAPE={:.2f}%{}",
            metrics["rmse"], metrics["mae"], metrics["mape"],
            f", MASE={metrics['mase']:.3f}" if metrics["mase"] is not None else ", MASE=N/A",
        )

        return metrics, False, None

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _fit_with_timeout(self, model: Prophet, data: pd.DataFrame, timeout_sec: int) -> bool:
        """Fit Prophet with per-fold timeout. Returns True if OK, False if timeout."""
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(model.fit, data)
        try:
            future.result(timeout=timeout_sec)
            return True
        except concurrent.futures.TimeoutError:
            return False
        finally:
            pool.shutdown(wait=False)

    def _aggregate_folds(
        self,
        rmse_folds: list[float],
        mae_folds: list[float],
        mape_folds: list[float],
        mase_folds: list[float | None],
        fold_indices: list[int],
    ) -> dict:
        """Aggregate fold metrics with optional progressive weighting."""
        if self.cv_weights and len(self.cv_weights) >= self.n_splits:
            weights = [self.cv_weights[i] for i in fold_indices]
            mean_rmse = float(np.average(rmse_folds, weights=weights))
            mean_mae = float(np.average(mae_folds, weights=weights))
            mean_mape = float(np.average(mape_folds, weights=weights))
        else:
            mean_rmse = float(np.mean(rmse_folds))
            mean_mae = float(np.mean(mae_folds))
            mean_mape = float(np.mean(mape_folds))

        # MASE: average excluding None values
        valid_mase = [m for m in mase_folds if m is not None]
        if valid_mase:
            if self.cv_weights and len(self.cv_weights) >= self.n_splits:
                mase_weights = [
                    self.cv_weights[fold_indices[i]]
                    for i, m in enumerate(mase_folds) if m is not None
                ]
                mean_mase = float(np.average(valid_mase, weights=mase_weights))
            else:
                mean_mase = float(np.mean(valid_mase))
        else:
            mean_mase = None

        return {
            "rmse": mean_rmse,
            "mae": mean_mae,
            "mape": mean_mape,
            "mase": mean_mase,
        }


# Need pandas import for type hint in _fit_with_timeout
import pandas as pd  # noqa: E402
