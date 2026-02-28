"""Ensemble forecasting model: Prophet base + XGBoost residual correction."""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics

if TYPE_CHECKING:
    from prophet import Prophet
    from xgboost import XGBRegressor
from epiforecast.models.base import ForecastModel
from epiforecast.models.ensemble.helpers import (
    FEATURE_NAMES,
    calcular_metricas_ensemble,
    calcular_metricas_prophet_base,
    construir_features_xgb,
    construir_holidays,
    generar_predicciones_insample,
    preparar_datos_ensemble,
)
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


@register_model("ensemble")
class EnsembleForecaster(ForecastModel):
    """Ensemble: Prophet base + XGBoost sobre residuos (ForecastModel/LSP)."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str = "incrementos_total",
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # Config ensemble-specific
        self.cutoff: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE",
            self._conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"),
        )
        self.horizon: int = self._conf.get("HORIZON_ENSEMBLE", 52)

        # Prophet HP
        pb = self._conf.get("prophet_base", {})
        self._prophet_hp: dict[str, Any] = {
            "changepoint_prior_scale": pb.get("changepoint_prior_scale", 0.05),
            "seasonality_prior_scale": pb.get("seasonality_prior_scale", 0.1),
            "seasonality_mode": pb.get("seasonality_mode", "additive"),
        }
        yc = pb.get("yearly_custom", {})
        self._yearly_period: float = yc.get("period", 365.25)
        self._yearly_fourier: int = yc.get("fourier_order", 10)

        # XGBoost HP
        xgb_hp = self._conf.get("xgboost", {})
        self._xgb_hp: dict[str, Any] = {
            "n_estimators": xgb_hp.get("n_estimators", 200),
            "max_depth": xgb_hp.get("max_depth", 4),
            "learning_rate": xgb_hp.get("learning_rate", 0.05),
            "subsample": xgb_hp.get("subsample", 0.8),
            "colsample_bytree": xgb_hp.get("colsample_bytree", 0.8),
        }

        # Holidays
        self._holidays: pd.DataFrame = construir_holidays(self._conf)

        # Internal state
        self._prophet: Prophet | None = None  # lazy import
        self._xgb: XGBRegressor | None = None  # lazy import
        self._feature_names: list[str] = list(FEATURE_NAMES)

        # Data placeholders (set during run())
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()
        self.pred_train: pd.DataFrame = pd.DataFrame()
        self.pred_test: pd.DataFrame = pd.DataFrame()
        self._t_prophet: float = 0.0
        self._t_ensemble: float = 0.0

    # ── ForecastModel Interface ────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame) -> None:
        """Entrena Prophet base + XGBoost sobre residuos."""
        from prophet import Prophet as _Prophet
        from xgboost import XGBRegressor as _XGBRegressor

        t0 = time.perf_counter()
        np.random.seed(RANDOM_SEED)

        # 1) Prophet base
        self._prophet = _Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=self._holidays if not self._holidays.empty else None,
            **self._prophet_hp,
        )
        self._prophet.add_seasonality(
            name="yearly_custom",
            period=self._yearly_period,
            fourier_order=self._yearly_fourier,
        )
        self._prophet.fit(train_data)
        self._t_prophet = time.perf_counter() - t0
        logger.info("  Prophet base entrenado en {:.1f}s", self._t_prophet)

        # 2) XGBoost sobre residuos
        t1 = time.perf_counter()
        prophet_train = self._prophet.predict(train_data[["ds"]])
        residuos = train_data["y"].values - prophet_train["yhat"].values

        feats_train = construir_features_xgb(
            train_data["y"].reset_index(drop=True),
            train_data["ds"].reset_index(drop=True),
        )
        valid_mask = feats_train.notna().all(axis=1)

        self._xgb = _XGBRegressor(**self._xgb_hp, n_jobs=-1, random_state=RANDOM_SEED)
        self._xgb.fit(feats_train[valid_mask], residuos[valid_mask.values])
        self._t_ensemble = time.perf_counter() - t1
        logger.info("  XGBoost residual entrenado en {:.1f}s", self._t_ensemble)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Genera pronostico a futuro (Prophet + XGBoost iterativo)."""
        if self._prophet is None or self._xgb is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")

        last_train = pd.Timestamp(self._prophet.history["ds"].max())
        last_real = self.serie["ds"].max() if not self.serie.empty else last_train
        weeks_test = max(int(np.ceil((last_real - last_train).days / 7)), 0)

        future = self._prophet.make_future_dataframe(periods=weeks_test + horizon, freq="W-MON")
        prophet_future = self._prophet.predict(future)
        mask_futuro = prophet_future["ds"] > last_real
        future_dates = prophet_future.loc[mask_futuro, "ds"].values
        future_yhat_prophet = prophet_future.loc[mask_futuro, "yhat"].values

        # XGBoost iterativo
        if not self.serie.empty:
            y_ext = self.serie["y"].values.tolist()
            d_ext = self.serie["ds"].values.tolist()
        else:
            y_ext = self._prophet.history["y"].values.tolist()
            d_ext = self._prophet.history["ds"].values.tolist()

        xgb_adj: list[float] = []
        for i in range(len(future_dates)):
            feats = construir_features_xgb(pd.Series(y_ext), pd.Series(pd.to_datetime(d_ext)))
            adj = float(self._xgb.predict(feats.iloc[[-1]].fillna(0))[0])
            xgb_adj.append(adj)
            y_ext.append(float(future_yhat_prophet[i]))
            d_ext.append(future_dates[i])

        ensemble_future = future_yhat_prophet + np.array(xgb_adj)
        return pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": ensemble_future,
                "yhat_lower": ensemble_future,
                "yhat_upper": ensemble_future,
                "yhat_prophet": future_yhat_prophet,
                "yhat_ensemble": ensemble_future,
            }
        )

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Evalua Prophet+XGB sobre ``data`` (hold-out temporal)."""
        if "y" in data.columns and not data.empty:
            test_df = data
        elif not self.test_data.empty:
            test_df = self.test_data
        else:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        if self._prophet is None or self._xgb is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        prophet_pred = self._prophet.predict(test_df[["ds"]])
        full_y = pd.concat([self.train_data["y"], test_df["y"]], ignore_index=True)
        full_ds = pd.concat([self.train_data["ds"], test_df["ds"]], ignore_index=True)
        feats_test = construir_features_xgb(full_y, full_ds).iloc[len(self.train_data) :].fillna(0)
        y_pred = prophet_pred["yhat"].values + self._xgb.predict(feats_test)

        metrics = compute_forecast_metrics(
            test_df["y"].to_numpy(), y_pred, self.train_data["y"].to_numpy()
        )
        return {
            "rmse": metrics["rmse"] or 0.0,
            "mae": metrics["mae"] or 0.0,
            "smape": metrics["smape"] or 0.0,
            "mase": metrics["mase"] if metrics["mase"] is not None else 0.0,
        }

    def save(self, path: Path) -> None:
        """Serializa Prophet + XGBoost + params a pickle."""
        if self._prophet is None or self._xgb is None:
            raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prophet": self._prophet,
            "xgb": self._xgb,
            "params": self.get_params(),
            "features": self._feature_names,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)
        logger.info("Modelo ensemble guardado: {}", path)

    def load(self, path: Path) -> None:
        """Restaura Prophet + XGBoost desde pickle."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301
        self._prophet = payload["prophet"]
        self._xgb = payload["xgb"]
        self._feature_names = payload.get("features", list(FEATURE_NAMES))
        logger.info("Modelo ensemble cargado: {}", path)

    def get_params(self) -> dict[str, Any]:
        """Retorna hiperparametros de ambos sub-modelos."""
        return {
            "prophet": self._prophet_hp,
            "xgboost": self._xgb_hp,
            "yearly_period": self._yearly_period,
            "yearly_fourier": self._yearly_fourier,
            "cutoff": self.cutoff,
            "horizon": self.horizon,
        }

    # ── Orchestration ──────────────────────────────────────────────────

    def run(self) -> tuple[Any, dict, dict]:
        """Pipeline completo: preparar datos -> fit -> evaluar."""
        self.serie, self.train_data, self.test_data = preparar_datos_ensemble(
            self.df, self.padecimiento, self.sexo, self.cutoff
        )
        self.fit(self.train_data)
        self.pred_train, self.pred_test = generar_predicciones_insample(
            self._prophet, self._xgb, self.train_data, self.test_data
        )
        metrics = calcular_metricas_ensemble(
            self.test_data,
            self.pred_test,
            self.train_data,
            "Ensemble (Prophet + XGBoost)",
            self.tiempo_total,
        )
        return self._prophet, metrics, self.get_params()

    # ── Accessors ──────────────────────────────────────────────────────

    @property
    def prophet_model(self) -> Prophet:
        if self._prophet is None:
            raise RuntimeError("Prophet no entrenado.")
        return self._prophet

    @property
    def xgb_model(self) -> XGBRegressor:
        if self._xgb is None:
            raise RuntimeError("XGBoost no entrenado.")
        return self._xgb

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    @property
    def tiempo_prophet(self) -> float:
        return self._t_prophet

    @property
    def tiempo_total(self) -> float:
        return self._t_prophet + self._t_ensemble

    def get_prophet_metrics(self) -> dict[str, Any]:
        """Metricas del Prophet base solo (sin XGBoost) sobre test set."""
        return calcular_metricas_prophet_base(
            self.test_data, self.pred_test, self.train_data, self._t_prophet
        )

    def generar_futuro(self) -> pd.DataFrame:
        return self.predict(self.horizon)
