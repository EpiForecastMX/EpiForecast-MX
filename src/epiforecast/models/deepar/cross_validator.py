# src/epiforecast/models/deepar/cross_validator.py
"""DeepAR cross-validator with temporal folds (SRP: CV only).

Uses TimeSeriesSplit for temporal cross-validation.
Trains with reduced epochs per fold for speed.
Computes RMSE, MAE, MAPE, SMAPE, MASE (same metrics as Prophet CV).

Supports both single-series and multi-series (32 states) modes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import pandas as pd
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

    def __init__(self, forecaster: DeepARForecaster, config: dict[str, Any] | None = None):
        _conf = config if config is not None else conf
        self.forecaster = forecaster
        # Cohortes de historia corta (p.ej. Dengue) usan CV mas ligera para que los folds
        # sigan siendo lo bastante largos para entrenar DeepAR (ver deepar.yaml short_series).
        self.n_splits: int = forecaster.cv_n_splits_override or _conf.get("TS_SPLITS", 4)
        self.test_size: int = forecaster.cv_test_size_override or _conf.get("TEST_SIZE", 53)

        # Reduced epochs for CV folds (at least 25 for convergence)
        full_epochs = forecaster.epochs
        self.cv_epochs: int = max(25, full_epochs // 4)

    def run(self) -> dict[str, Any]:
        """Run temporal CV across all folds and return averaged metrics."""
        train_data = self.forecaster.train_data

        if train_data.empty or len(train_data) < self.test_size + 52:
            logger.warning("Datos insuficientes para CV DeepAR ({} filas)", len(train_data))
            return {"rmse": None, "mae": None, "mape": None, "smape": None, "mase": None}

        if self.forecaster._is_multi_series and not self.forecaster.train_data_multi.empty:
            return self._run_multi_series()
        return self._run_single_series()

    # ── Single-series CV ─────────────────────────────────────────────────────

    def _run_single_series(self) -> dict[str, Any]:
        """Original single-series CV using row-index splits."""
        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=self.test_size)
        train_data = self.forecaster.train_data

        rmse_folds: list[float] = []
        mae_folds: list[float] = []
        mape_folds: list[float] = []
        smape_folds: list[float] = []
        mase_folds: list[float | None] = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_data)):
            train_fold = train_data.iloc[train_idx]
            val_fold = train_data.iloc[val_idx]

            logger.debug(
                "DeepAR CV Fold {}/{}: Train {} -> {}, Val {} -> {}",
                fold_idx + 1,
                self.n_splits,
                train_fold["ds"].min().date(),
                train_fold["ds"].max().date(),
                val_fold["ds"].min().date(),
                val_fold["ds"].max().date(),
            )

            try:
                metrics = self._evaluate_fold(train_fold, val_fold, fold_idx)
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
            except (RuntimeError, ValueError) as e:
                logger.warning("Error en fold {}: {}", fold_idx + 1, e)

        return self._aggregate_fold_metrics(
            rmse_folds, mae_folds, mape_folds, smape_folds, mase_folds
        )

    # ── Multi-series CV ──────────────────────────────────────────────────────

    def _run_multi_series(self) -> dict[str, Any]:
        """Multi-series CV: date-based splits across all 32 states.

        Uses the aggregated national series to determine fold date boundaries,
        then applies them to all 32 states.  Metrics are evaluated on the
        aggregated national forecast (sum of state forecasts).
        """
        train_national = self.forecaster.train_data
        train_multi = self.forecaster.train_data_multi

        # Split on unique dates of the national series
        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=self.test_size)
        unique_dates = sorted(train_national["ds"].unique())

        rmse_folds: list[float] = []
        mae_folds: list[float] = []
        mape_folds: list[float] = []
        smape_folds: list[float] = []
        mase_folds: list[float | None] = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(unique_dates)):
            train_cutoff = unique_dates[train_idx[-1]]
            val_start = unique_dates[val_idx[0]]
            val_end = unique_dates[val_idx[-1]]

            # Split multi-series by date
            train_fold_multi = train_multi[train_multi["ds"] <= train_cutoff]

            # National series for metric evaluation
            train_fold_national = train_national[train_national["ds"] <= train_cutoff]
            val_fold_national = train_national[
                (train_national["ds"] >= val_start) & (train_national["ds"] <= val_end)
            ]

            logger.debug(
                "DeepAR Multi-CV Fold {}/{}: Train -> {}, Val {} -> {} ({} semanas)",
                fold_idx + 1,
                self.n_splits,
                train_cutoff.date(),
                val_start.date(),
                val_end.date(),
                len(val_idx),
            )

            try:
                metrics = self._evaluate_fold_multi(
                    train_fold_multi,
                    val_fold_national,
                    train_fold_national,
                    len(val_idx),
                    fold_idx,
                )
                rmse_folds.append(metrics["rmse"])
                mae_folds.append(metrics["mae"])
                mape_folds.append(metrics["mape"])
                smape_folds.append(metrics["smape"])
                mase_folds.append(metrics["mase"])

                logger.debug(
                    "Multi-CV Fold {}: RMSE={:.4f} MAE={:.4f} MAPE={:.2f}%",
                    fold_idx + 1,
                    metrics["rmse"],
                    metrics["mae"],
                    metrics["mape"],
                )
            except (RuntimeError, ValueError) as e:
                logger.warning("Error en multi-CV fold {}: {}", fold_idx + 1, e)

        return self._aggregate_fold_metrics(
            rmse_folds, mae_folds, mape_folds, smape_folds, mase_folds
        )

    # ── Fold evaluators ──────────────────────────────────────────────────────

    def _evaluate_fold(
        self,
        train_fold: pd.DataFrame,
        val_fold: pd.DataFrame,
        fold_idx: int = 0,
    ) -> dict[str, Any]:
        """Train single-series DeepAR on a fold and compute metrics."""
        import torch

        torch.manual_seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        dataset = self.forecaster._build_dataset(train_fold)

        estimator = self.forecaster._create_estimator(
            epochs=self.cv_epochs,
            prediction_length=len(val_fold),
            early_stopping=False,
            phase=f"CV {fold_idx + 1}/{self.n_splits}",
        )
        predictor = estimator.train(dataset)

        forecasts = list(predictor.predict(dataset, num_samples=self.forecaster.num_samples))
        fc = forecasts[0]
        yhat_raw = fc.mean[: len(val_fold)]

        # Metricas en espacio de conteos reales (desnormalizar tasa)
        normalizar = self.forecaster._conf.get("normalizar_tasa", True)
        if normalizar and "y_original" in val_fold.columns and "Total" in val_fold.columns:
            pob = val_fold["Total"].iloc[0]
            tasa_por = self.forecaster._conf.get("tasa_por", 100000)
            y_true = val_fold["y_original"].to_numpy()[: len(yhat_raw)]
            yhat = (yhat_raw * pob) / tasa_por
            y_train = train_fold["y_original"].to_numpy()
        else:
            y_true = val_fold["y"].to_numpy()[: len(yhat_raw)]
            yhat = yhat_raw
            y_train = train_fold["y"].to_numpy()

        return self._compute_metrics(y_true, yhat, y_train)

    def _evaluate_fold_multi(
        self,
        train_fold_multi: pd.DataFrame,
        val_fold_national: pd.DataFrame,
        train_fold_national: pd.DataFrame,
        n_val_weeks: int,
        fold_idx: int = 0,
    ) -> dict[str, Any]:
        """Train multi-series DeepAR on a fold, aggregate, compute metrics."""
        import torch

        torch.manual_seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        dataset = self.forecaster._build_multi_dataset(train_fold_multi)

        estimator = self.forecaster._create_estimator(
            epochs=self.cv_epochs,
            prediction_length=n_val_weeks,
            early_stopping=False,
            phase=f"CV {fold_idx + 1}/{self.n_splits}",
        )
        predictor = estimator.train(dataset)

        forecasts = list(predictor.predict(dataset, num_samples=self.forecaster.num_samples))

        # Aggregate: convertir tasa->conteo por estado, sumar a nacional
        all_samples = np.stack([fc.samples for fc in forecasts], axis=0)

        normalizar = self.forecaster._conf.get("normalizar_tasa", True)
        if normalizar and "Total" in train_fold_multi.columns:
            tasa_por = self.forecaster._conf.get("tasa_por", 100000)
            mapa_pob = train_fold_multi.groupby("item_id")["Total"].last().to_dict()
            items = [fc.item_id for fc in forecasts]
            # Convertir tasa->conteo, sumar (quedarse en conteos nacionales)
            for i, item_id in enumerate(items):
                pob = mapa_pob.get(item_id, 0)
                if pob > 0:
                    all_samples[i] = (all_samples[i] * pob) / tasa_por
            national_samples = all_samples.sum(axis=0)  # conteo nacional
        else:
            national_samples = all_samples.sum(axis=0)

        yhat = national_samples.mean(axis=0)[:n_val_weeks]

        # Metricas en espacio de conteos reales
        if "y_original" in val_fold_national.columns:
            y_true = val_fold_national["y_original"].to_numpy()[: len(yhat)]
            y_train = train_fold_national["y_original"].to_numpy()
        else:
            y_true = val_fold_national["y"].to_numpy()[: len(yhat)]
            y_train = train_fold_national["y"].to_numpy()

        return self._compute_metrics(y_true, yhat, y_train)

    # ── Shared helpers ───────────────────────────────────────────────────────

    def _compute_metrics(
        self,
        y_true: npt.NDArray[np.floating[Any]],
        yhat: npt.NDArray[np.floating[Any]],
        y_train: npt.NDArray[np.floating[Any]],
    ) -> dict[str, Any]:
        """Compute RMSE, MAE, MAPE, SMAPE, MASE from arrays."""
        from epiforecast.evaluation.metrics import compute_forecast_metrics

        return compute_forecast_metrics(y_true, yhat, y_train)

    def _aggregate_fold_metrics(
        self,
        rmse_folds: list[float],
        mae_folds: list[float],
        mape_folds: list[float],
        smape_folds: list[float],
        mase_folds: list[float | None],
    ) -> dict[str, Any]:
        """Average metrics across CV folds."""
        if not rmse_folds:
            return {"rmse": None, "mae": None, "mape": None, "smape": None, "mase": None}

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
