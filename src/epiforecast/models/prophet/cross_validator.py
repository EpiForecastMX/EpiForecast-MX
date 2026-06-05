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
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.model_selection import TimeSeriesSplit

from epiforecast.constants import RANDOM_SEED
from epiforecast.utils.cohorts import is_neuro
from epiforecast.utils.config import conf, logger

if TYPE_CHECKING:
    from epiforecast.models.prophet.model import ProphetForecaster


class ProphetCrossValidator:
    """Temporal cross-validator for Prophet models.

    Evaluates one HP combination across multiple folds with
    optional progressive weighting and Newton timeout protection.
    """

    def __init__(self, forecaster: ProphetForecaster, config: dict[str, Any] | None = None):
        """Inicializa el cross-validator con configuración de folds y timeouts.

        Args:
            forecaster: Instancia de ProphetForecaster con datos de entrenamiento.
            config:     Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.forecaster = forecaster
        self.n_splits: int = _conf["TS_SPLITS"]
        self.test_size: int = _conf["TEST_SIZE"]
        # cv_weights despenaliza el fold COVID (0.5); solo aplica a la cohorte neuro.
        # Padecimientos fuera de NEURO_CONDITIONS (Dengue) usan pesos uniformes (None):
        # 2020-2022 no fue un periodo atípico para una arbovirosis.
        _cv_weights = _conf.get("cv_weights", None)
        if not is_neuro(getattr(forecaster, "padecimiento", None)):
            _cv_weights = None
        self.cv_weights: list[float] | None = _cv_weights
        self.fold_timeout: int = _conf.get("cv_timeout_por_fold", 0)

    def run(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run full CV by delegating to ProphetTuner.

        This is called from ProphetForecaster.cross_validate().
        """
        from epiforecast.models.prophet.tuner import ProphetTuner

        tuner = ProphetTuner(self.forecaster)
        return tuner.run()

    def evaluate_combo(
        self,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], bool, float | None]:
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

        fold_results = _FoldCollector()
        cp = params.get("changepoint_prior_scale", 0)
        timed_out = False
        newton_cp: float | None = None

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_data)):
            train_fold = train_data.iloc[train_idx]
            val_fold = train_data.iloc[val_idx]

            logger.debug(
                "Fold {}: Train hasta {}, Val {} → {}",
                fold_idx + 1,
                train_fold["ds"].max().date(),
                val_fold["ds"].min().date(),
                val_fold["ds"].max().date(),
            )

            timed_out, newton_cp = self._run_single_fold(
                params,
                train_fold,
                val_fold,
                fold_idx,
                cp,
                fold_results,
            )
            if timed_out:
                break

        if timed_out or fold_results.is_empty():
            return (
                {
                    "rmse": float("inf"),
                    "mae": float("inf"),
                    "mape": float("inf"),
                    "smape": float("inf"),
                    "mase": None,
                },
                timed_out,
                newton_cp,
            )

        metrics = self._aggregate_folds(
            fold_results.rmse,
            fold_results.mae,
            fold_results.mape,
            fold_results.smape,
            fold_results.mase,
            fold_results.indices,
        )

        logger.debug(
            "Métricas CV: RMSE={:.4f}, MAE={:.4f}, MAPE={:.2f}%, SMAPE={:.2f}%{}",
            metrics["rmse"],
            metrics["mae"],
            metrics["mape"],
            metrics["smape"],
            f", MASE={metrics['mase']:.3f}" if metrics["mase"] is not None else ", MASE=N/A",
        )

        return metrics, False, None

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _run_single_fold(
        self,
        params: dict[str, Any],
        train_fold: pd.DataFrame,
        val_fold: pd.DataFrame,
        fold_idx: int,
        cp: float,
        collector: _FoldCollector,
    ) -> tuple[bool, float | None]:
        """Ejecuta un fold de CV: fit, predict, métricas. Retorna (timed_out, newton_cp)."""
        try:
            model = self.forecaster._create_prophet(**params)

            if self.fold_timeout:
                np.random.seed(RANDOM_SEED)
                fit_ok = self._fit_with_timeout(model, train_fold, self.fold_timeout)
                if not fit_ok:
                    logger.debug(
                        "Timeout fold: >{:.0f}s en fold {}/{}. Newton → skip cp ≤ {}",
                        self.fold_timeout,
                        fold_idx + 1,
                        self.n_splits,
                        cp,
                    )
                    return True, cp
            else:
                np.random.seed(RANDOM_SEED)
                model.fit(train_fold)

            metrics = _compute_fold_metrics(
                model,
                train_fold,
                val_fold,
                poblacion=self.forecaster.poblacion_valor,
                tasa_por=self.forecaster.tasa_por,
                log_transform=self.forecaster.log_transform,
            )
            collector.append(fold_idx, metrics)

        except (RuntimeError, ValueError) as e:
            logger.debug("Excepción en fold {}: {}", fold_idx + 1, e)

        return False, None

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
        smape_folds: list[float],
        mase_folds: list[float | None],
        fold_indices: list[int],
    ) -> dict[str, Any]:
        """Aggregate fold metrics with optional progressive weighting."""
        if self.cv_weights and len(self.cv_weights) >= self.n_splits:
            weights = [self.cv_weights[i] for i in fold_indices]
            mean_rmse = float(np.average(rmse_folds, weights=weights))
            mean_mae = float(np.average(mae_folds, weights=weights))
            mean_mape = float(np.average(mape_folds, weights=weights))
            mean_smape = float(np.average(smape_folds, weights=weights))
        else:
            mean_rmse = float(np.mean(rmse_folds))
            mean_mae = float(np.mean(mae_folds))
            mean_mape = float(np.mean(mape_folds))
            mean_smape = float(np.mean(smape_folds))

        # MASE: average excluding None values
        valid_mase = [m for m in mase_folds if m is not None]
        if valid_mase:
            if self.cv_weights and len(self.cv_weights) >= self.n_splits:
                mase_weights = [
                    self.cv_weights[fold_indices[i]]
                    for i, m in enumerate(mase_folds)
                    if m is not None
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
            "smape": mean_smape,
            "mase": mean_mase,
        }


# ── Module-level helpers ─────────────────────────────────────────────────


class _FoldCollector:
    """Acumula métricas de cada fold de CV."""

    def __init__(self) -> None:
        """Inicializa las listas vacías para acumular métricas por fold."""
        self.rmse: list[float] = []
        self.mae: list[float] = []
        self.mape: list[float] = []
        self.smape: list[float] = []
        self.mase: list[float | None] = []
        self.indices: list[int] = []

    def append(self, fold_idx: int, metrics: dict[str, Any]) -> None:
        """Agrega las métricas de un fold."""
        self.rmse.append(metrics["rmse"])
        self.mae.append(metrics["mae"])
        self.mape.append(metrics["mape"])
        self.smape.append(metrics["smape"])
        self.mase.append(metrics["mase"])
        self.indices.append(fold_idx)

    def is_empty(self) -> bool:
        """Verifica si no se acumularon resultados."""
        return len(self.rmse) == 0


def _compute_fold_metrics(
    model: Prophet,
    train_fold: pd.DataFrame,
    val_fold: pd.DataFrame,
    poblacion: float | None = None,
    tasa_por: int = 100000,
    log_transform: bool = False,
) -> dict[str, Any]:
    """Calcula RMSE, MAE, MAPE, SMAPE y MASE para un fold de CV.

    Si ``poblacion`` es proporcionada, convierte predicciones y reales a
    espacio de conteos para metricas significativas en enfermedades raras.
    """
    from epiforecast.evaluation.metrics import compute_forecast_metrics

    pred_cols = ["ds", "oni"] if "oni" in val_fold.columns else ["ds"]
    forecast = model.predict(val_fold[pred_cols])
    merged = val_fold[["ds", "y"]].merge(forecast[["ds", "yhat"]], on="ds")

    if poblacion is not None and "y_original" in val_fold.columns:
        # Metricas en espacio de conteos reales
        merged_orig = val_fold[["ds", "y_original"]].merge(forecast[["ds", "yhat"]], on="ds")
        y_true = merged_orig["y_original"].to_numpy()
        yhat_tasa = merged_orig["yhat"].to_numpy()
        if log_transform:
            yhat_tasa = np.expm1(yhat_tasa)
        y_pred = (yhat_tasa * poblacion) / tasa_por
        y_train = train_fold["y_original"].to_numpy()
    else:
        y_true = merged["y"].to_numpy()
        y_pred = merged["yhat"].to_numpy()
        y_train = train_fold["y"].to_numpy()

    return compute_forecast_metrics(y_true, y_pred, y_train)
