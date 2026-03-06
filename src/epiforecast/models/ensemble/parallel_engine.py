"""Motor de prediccion paralela: Prophet + XGBDirect con pesos Ridge OOF.

Extraido de model.py para cumplir SRP (max 300 lineas por modulo).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.config import logger


class ParallelEngine:
    """Coordina predicciones paralelas Prophet + XGBDirect con pesos OOF."""

    def __init__(
        self,
        prophet_hp: dict[str, Any],
        yearly_period: float,
        yearly_fourier: int,
        holidays: pd.DataFrame,
        xgb_hp: dict[str, Any],
        parallel_alpha: float,
        parallel_oof_folds: int,
        parallel_oof_cutoff: str,
        parallel_min_train_weeks: int,
    ) -> None:
        self._prophet_hp = prophet_hp
        self._yearly_period = yearly_period
        self._yearly_fourier = yearly_fourier
        self._holidays = holidays
        self._xgb_hp = xgb_hp
        self._parallel_alpha = parallel_alpha
        self._parallel_oof_folds = parallel_oof_folds
        self._parallel_oof_cutoff = parallel_oof_cutoff
        self._parallel_min_train_weeks = parallel_min_train_weeks
        self._xgb_direct: Any = None
        self._ensemble_weights: npt.NDArray[np.floating[Any]] | None = None
        self._t_ensemble: float = 0.0

    def fit(self, prophet: Any, train_data: pd.DataFrame) -> None:
        """Entrena XGBDirect + aprende pesos [w_prophet, w_xgb] via OOF."""
        import time

        from epiforecast.models.ensemble.weight_optimizer import EnsembleWeightOptimizer
        from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster

        t1 = time.perf_counter()
        self._xgb_direct = XGBDirectForecaster(self._xgb_hp)
        self._xgb_direct.fit(train_data)
        optimizer = EnsembleWeightOptimizer(
            alpha=self._parallel_alpha,
            n_folds=self._parallel_oof_folds,
            min_train_weeks=self._parallel_min_train_weeks,
        )
        self._ensemble_weights = optimizer.fit_oof(
            train_data,
            prophet_builder=self._build_prophet_temp,
            xgb_builder=self._build_xgb_direct_temp,
            oof_cutoff=self._parallel_oof_cutoff,
        )
        self._t_ensemble = time.perf_counter() - t1
        logger.debug("  Parallel ensemble entrenado en {:.1f}s", self._t_ensemble)

    def _build_prophet_temp(self, train_df: pd.DataFrame) -> Any:
        """Construye un Prophet temporal para OOF."""
        from prophet import Prophet as _Prophet

        np.random.seed(RANDOM_SEED)
        m = _Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=self._holidays if not self._holidays.empty else None,
            **self._prophet_hp,
        )
        m.add_seasonality(
            name="yearly_custom",
            period=self._yearly_period,
            fourier_order=self._yearly_fourier,
        )
        m.fit(train_df)
        return m

    def _build_xgb_direct_temp(self, train_df: pd.DataFrame) -> Any:
        """Construye un XGBDirect temporal para OOF."""
        from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster

        xgb = XGBDirectForecaster(self._xgb_hp)
        xgb.fit(train_df)
        return xgb

    def predict(self, prophet: Any, serie: pd.DataFrame, horizon: int = 52) -> pd.DataFrame:
        """Prediccion paralela: w[0]*prophet + w[1]*xgb_direct."""
        if self._xgb_direct is None or self._ensemble_weights is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")
        w = self._ensemble_weights
        last_train = pd.Timestamp(prophet.history["ds"].max())
        last_real = serie["ds"].max() if not serie.empty else last_train
        weeks_beyond = max(int(np.ceil((last_real - last_train).days / 7)), 0)
        future_df = prophet.make_future_dataframe(periods=weeks_beyond + horizon, freq="W-MON")
        prophet_full = prophet.predict(future_df)
        xgb_insample = self._xgb_direct.predict_insample(serie)
        prophet_in = prophet_full[prophet_full["ds"].isin(serie["ds"].values)]
        yhat_p_in = prophet_in["yhat"].values[: len(serie)]
        yhat_in = np.clip(w[0] * yhat_p_in + w[1] * xgb_insample, 0, None)
        mask_fut = prophet_full["ds"] > last_real
        fut_dates = prophet_full.loc[mask_fut, "ds"].values
        yhat_p_fut = prophet_full.loc[mask_fut, "yhat"].values
        xgb_future = self._xgb_direct.predict_recursive(serie, fut_dates)
        yhat_fut = np.clip(w[0] * yhat_p_fut + w[1] * xgb_future, 0, None)
        all_ds = np.concatenate([serie["ds"].values, fut_dates])
        all_yhat = np.concatenate([yhat_in, yhat_fut])
        return pd.DataFrame(
            {
                "ds": all_ds,
                "yhat": all_yhat,
                "yhat_lower": all_yhat,
                "yhat_upper": all_yhat,
                "yhat_prophet": np.concatenate([yhat_p_in, yhat_p_fut]),
                "yhat_ensemble": all_yhat,
            }
        )

    def cross_validate(
        self,
        prophet: Any,
        test_df: pd.DataFrame,
        train_data: pd.DataFrame,
    ) -> dict[str, float]:
        """Evalua modo paralelo sobre test_df (prediccion recursiva)."""
        if self._xgb_direct is None or self._ensemble_weights is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}
        w = self._ensemble_weights
        p_pred = prophet.predict(test_df[["ds"]])["yhat"].values
        x_pred = self._xgb_direct.predict_recursive(train_data, test_df["ds"].values)
        y_pred = np.clip(w[0] * p_pred + w[1] * x_pred, 0, None)
        y_train = train_data["y"].to_numpy() if not train_data.empty else np.array([0.0])
        metrics = compute_forecast_metrics(test_df["y"].to_numpy(), y_pred, y_train)
        return {
            "rmse": metrics["rmse"] or 0.0,
            "mae": metrics["mae"] or 0.0,
            "smape": metrics["smape"] or 0.0,
            "mase": metrics["mase"] if metrics["mase"] is not None else 0.0,
        }

    def gen_insample_preds(
        self,
        prophet: Any,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Genera pred_train y pred_test para modo paralelo."""
        w = self._ensemble_weights
        if w is None or self._xgb_direct is None:
            return pd.DataFrame(), pd.DataFrame()
        yhat_p = prophet.predict(train_data[["ds"]])["yhat"].values
        yhat_x = self._xgb_direct.predict_insample(train_data)
        pred_train = pd.DataFrame(
            {
                "ds": train_data["ds"].values,
                "yhat_prophet": yhat_p,
                "yhat_ensemble": np.clip(w[0] * yhat_p + w[1] * yhat_x, 0, None),
            }
        )
        pred_test = pd.DataFrame()
        if not test_data.empty:
            yhat_p_t = prophet.predict(test_data[["ds"]])["yhat"].values
            yhat_x_t = self._xgb_direct.predict_recursive(train_data, test_data["ds"].values)
            pred_test = pd.DataFrame(
                {
                    "ds": test_data["ds"].values,
                    "yhat_prophet": yhat_p_t,
                    "yhat_ensemble": np.clip(w[0] * yhat_p_t + w[1] * yhat_x_t, 0, None),
                }
            )
        return pred_train, pred_test

    @property
    def xgb_direct(self) -> Any:
        return self._xgb_direct

    @property
    def weights(self) -> npt.NDArray[np.floating[Any]] | None:
        return self._ensemble_weights

    @property
    def t_ensemble(self) -> float:
        return self._t_ensemble

    def get_params(self) -> dict[str, Any]:
        """Retorna pesos para reporting."""
        if self._ensemble_weights is None:
            return {}
        return {
            "w_prophet": round(float(self._ensemble_weights[0]), 4),
            "w_xgb": round(float(self._ensemble_weights[1]), 4),
        }
