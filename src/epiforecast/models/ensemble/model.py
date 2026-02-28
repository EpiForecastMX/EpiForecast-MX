# src/epiforecast/models/ensemble/model.py
"""Ensemble forecasting model: Prophet base + XGBoost residual correction (SRP).

Target = conteos absolutos (incrementos), NO tasa por 100k.
El XGBoost captura volatilidad y picos que Prophet pierde.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd
from prophet import Prophet
from xgboost import XGBRegressor

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import mae, mase, rmse, smape
from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True

# Features que construye XGBoost
_FEATURE_NAMES: list[str] = [
    "lag_1",
    "lag_2",
    "lag_4",
    "roll_4",
    "roll_8",
    "roll_12",
    "month",
    "week_of_year",
]


def _construir_features_xgb(y_series: pd.Series, dates: pd.Series) -> pd.DataFrame:
    """Construye features temporales y de lags para XGBoost."""
    feats = pd.DataFrame(index=y_series.index)
    feats["lag_1"] = y_series.shift(1)
    feats["lag_2"] = y_series.shift(2)
    feats["lag_4"] = y_series.shift(4)
    feats["roll_4"] = y_series.rolling(4).mean()
    feats["roll_8"] = y_series.rolling(8).mean()
    feats["roll_12"] = y_series.rolling(12).mean()
    feats["month"] = dates.dt.month
    feats["week_of_year"] = dates.dt.isocalendar().week.astype(int).values
    return feats


def _construir_holidays(config: dict[str, Any]) -> pd.DataFrame:
    """Construye DataFrame de holidays desde config (periodos atipicos)."""
    periodos = config.get("peridos_atipicos", [])
    if not periodos:
        return pd.DataFrame(columns=["holiday", "ds", "lower_window", "upper_window"])

    rows = []
    for p in periodos:
        rows.append(
            {
                "holiday": p["holiday"],
                "ds": pd.Timestamp(p["ds"]),
                "lower_window": p.get("lower_window", 0),
                "upper_window": p.get("upper_window", 0),
            }
        )
    return pd.DataFrame(rows)


@register_model("ensemble")
class EnsembleForecaster(ForecastModel):
    """Ensemble: Prophet base + XGBoost sobre residuos.

    Implements ForecastModel interface (LSP). Se registra en la factory
    como ``create_model("ensemble")``.
    """

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
        self._holidays: pd.DataFrame = _construir_holidays(self._conf)

        # Internal state
        self._prophet: Prophet | None = None
        self._xgb: XGBRegressor | None = None
        self._feature_names: list[str] = list(_FEATURE_NAMES)

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
        """Entrena Prophet base + XGBoost sobre residuos.

        Args:
            train_data: DataFrame con columnas ``ds`` y ``y``.
        """
        t0 = time.perf_counter()
        np.random.seed(RANDOM_SEED)

        # 1) Prophet base
        self._prophet = Prophet(
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
        yhat_train = prophet_train["yhat"].values
        residuos = train_data["y"].values - yhat_train

        feats_train = _construir_features_xgb(
            train_data["y"].reset_index(drop=True),
            train_data["ds"].reset_index(drop=True),
        )
        valid_mask = feats_train.notna().all(axis=1)
        feats_valid = feats_train[valid_mask]
        residuos_valid = residuos[valid_mask.values]

        self._xgb = XGBRegressor(
            **self._xgb_hp,
            n_jobs=-1,
            random_state=RANDOM_SEED,
        )
        self._xgb.fit(feats_valid, residuos_valid)
        self._t_ensemble = time.perf_counter() - t1
        logger.info("  XGBoost residual entrenado en {:.1f}s", self._t_ensemble)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Genera pronostico a futuro (Prophet + XGBoost iterativo).

        Returns:
            DataFrame con columnas: ds, yhat, yhat_lower, yhat_upper,
            yhat_prophet, yhat_ensemble.
        """
        if self._prophet is None or self._xgb is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")

        # Determinar ultimo dato real una sola vez
        last_train = pd.Timestamp(self._prophet.history["ds"].max())
        last_real = self.serie["ds"].max() if not self.serie.empty else last_train
        weeks_test = max(int(np.ceil((last_real - last_train).days / 7)), 0)
        periods_needed = weeks_test + horizon

        future = self._prophet.make_future_dataframe(periods=periods_needed, freq="W-MON")
        prophet_future = self._prophet.predict(future)
        mask_futuro = prophet_future["ds"] > last_real
        future_dates = prophet_future.loc[mask_futuro, "ds"].values
        future_yhat_prophet = prophet_future.loc[mask_futuro, "yhat"].values

        # XGBoost iterativo
        if not self.serie.empty:
            y_extended = self.serie["y"].values.tolist()
            dates_extended = self.serie["ds"].values.tolist()
        else:
            y_extended = self._prophet.history["y"].values.tolist()
            dates_extended = self._prophet.history["ds"].values.tolist()

        xgb_adjustments: list[float] = []
        for i in range(len(future_dates)):
            y_ser = pd.Series(y_extended)
            d_ser = pd.Series(pd.to_datetime(dates_extended))
            feats = _construir_features_xgb(y_ser, d_ser)
            last_feat = feats.iloc[[-1]].fillna(0)
            adj = float(self._xgb.predict(last_feat)[0])
            xgb_adjustments.append(adj)

            y_extended.append(float(future_yhat_prophet[i]))
            dates_extended.append(future_dates[i])

        ensemble_future = future_yhat_prophet + np.array(xgb_adjustments)

        return pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": ensemble_future,
                "yhat_lower": ensemble_future,  # sin IC por ahora
                "yhat_upper": ensemble_future,
                "yhat_prophet": future_yhat_prophet,
                "yhat_ensemble": ensemble_future,
            }
        )

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Evalua Prophet+XGB sobre ``data`` (hold-out temporal).

        Si ``data`` tiene columna ``y``, se usa como ground-truth.
        De lo contrario, usa ``self.test_data`` como fallback.
        """
        if "y" in data.columns and not data.empty:
            test_df = data
        elif not self.test_data.empty:
            test_df = self.test_data
        else:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        if self._prophet is None or self._xgb is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        # Generar predicciones sobre el DataFrame proporcionado
        prophet_pred = self._prophet.predict(test_df[["ds"]])
        yhat_prophet = prophet_pred["yhat"].values

        full_y = pd.concat([self.train_data["y"], test_df["y"]], ignore_index=True)
        full_ds = pd.concat([self.train_data["ds"], test_df["ds"]], ignore_index=True)
        feats_full = _construir_features_xgb(full_y, full_ds)
        feats_test = feats_full.iloc[len(self.train_data) :].fillna(0)
        y_pred = yhat_prophet + self._xgb.predict(feats_test)

        y_true = test_df["y"].values
        y_train = self.train_data["y"].values
        mase_val = mase(y_true, y_pred, y_train)
        return {
            "rmse": rmse(y_true, y_pred),
            "mae": mae(y_true, y_pred),
            "smape": smape(y_true, y_pred),
            "mase": mase_val if mase_val is not None else 0.0,
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
        self._feature_names = payload.get("features", list(_FEATURE_NAMES))
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
        """Pipeline completo: preparar datos -> fit -> evaluar.

        Returns:
            (prophet_model, metrics_ensemble, params) — primer elemento es
            el Prophet interno, consistente con ProphetForecaster.run().
        """
        # 1) Preparar datos: agrupa nacional, train/test split
        self._preparar_datos()

        # 2) Fit (Prophet + XGBoost)
        self.fit(self.train_data)

        # 3) Generar predicciones sobre train y test (para graficos + metricas)
        self._generar_predicciones_insample()

        # 4) Metricas sobre test set
        metrics_ensemble = self._calcular_metricas_test("Ensemble (Prophet + XGBoost)")

        return self._prophet, metrics_ensemble, self.get_params()

    # ── Accessors para el script ───────────────────────────────────────

    @property
    def prophet_model(self) -> Prophet:
        """Acceso al modelo Prophet interno."""
        if self._prophet is None:
            raise RuntimeError("Prophet no entrenado.")
        return self._prophet

    @property
    def xgb_model(self) -> XGBRegressor:
        """Acceso al modelo XGBoost interno."""
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
        if self.test_data.empty or self.pred_test.empty:
            return {
                "modelo": "Prophet Base",
                "rmse": 0.0,
                "mae": 0.0,
                "smape": 0.0,
                "mase": None,
                "tiempo": 0.0,
            }

        y_true = self.test_data["y"].values
        y_train = self.train_data["y"].values
        y_pred = self.pred_test["yhat_prophet"].values
        mase_val = mase(y_true, y_pred, y_train)
        return {
            "modelo": "Prophet Base",
            "rmse": rmse(y_true, y_pred),
            "mae": mae(y_true, y_pred),
            "smape": smape(y_true, y_pred),
            "mase": mase_val,
            "tiempo": self._t_prophet,
        }

    def generar_futuro(self) -> pd.DataFrame:
        """Genera DataFrame con pronostico a futuro para ambos sub-modelos."""
        return self.predict(self.horizon)

    # ── Private Helpers ────────────────────────────────────────────────

    def _preparar_datos(self) -> None:
        """Carga y prepara datos desde el DataFrame proporcionado."""
        if self.df.empty:
            raise ValueError("DataFrame vacio. Proporcionar df en __init__.")

        # Asegurar columna Fecha como datetime
        if "Fecha" in self.df.columns:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])

        # Resolver nombre del padecimiento en el CSV
        padecimiento_tipo = self.padecimiento or "General"
        if "Padecimiento" in self.df.columns:
            padecimientos_csv = self.df["Padecimiento"].unique()
            nombre_csv = padecimiento_tipo
            for p in padecimientos_csv:
                if (
                    p.lower().replace("\u00e9", "e").replace("\u00f3", "o")
                    == padecimiento_tipo.lower()
                ):
                    nombre_csv = p
                    break
            df_filtrado = self.df[self.df["Padecimiento"] == nombre_csv].copy()
        else:
            df_filtrado = self.df.copy()

        # Determinar columna de fecha
        col_fecha = "Fecha" if "Fecha" in df_filtrado.columns else "ds"

        # Agregar a nivel nacional si hay columna de sexo
        if self.sexo in df_filtrado.columns:
            self.serie = (
                df_filtrado.groupby(col_fecha, as_index=False)[self.sexo]
                .sum()
                .rename(columns={col_fecha: "ds", self.sexo: "y"})
                .sort_values("ds")
                .reset_index(drop=True)
            )
        elif "y" in df_filtrado.columns and "ds" in df_filtrado.columns:
            self.serie = df_filtrado[["ds", "y"]].copy().sort_values("ds").reset_index(drop=True)
        else:
            raise ValueError(
                f"No se encontro columna '{self.sexo}' ni 'y' en el DataFrame. "
                f"Columnas: {list(df_filtrado.columns)}"
            )

        # Train/test split
        cutoff = pd.Timestamp(self.cutoff)
        self.train_data = self.serie[self.serie["ds"] < cutoff].copy().reset_index(drop=True)
        self.test_data = self.serie[self.serie["ds"] >= cutoff].copy().reset_index(drop=True)

        logger.info(
            "  {} — Train: {} filas | Test: {} filas",
            padecimiento_tipo,
            len(self.train_data),
            len(self.test_data),
        )

    def _generar_predicciones_insample(self) -> None:
        """Genera predicciones in-sample (train + test) para graficos."""
        if self._prophet is None or self._xgb is None:
            return

        # Prophet in-sample sobre train
        prophet_train = self._prophet.predict(self.train_data[["ds"]])
        yhat_train_prophet = prophet_train["yhat"].values

        # XGBoost ajuste sobre train
        feats_train = _construir_features_xgb(
            self.train_data["y"].reset_index(drop=True),
            self.train_data["ds"].reset_index(drop=True),
        )
        valid_mask = feats_train.notna().all(axis=1)
        xgb_adj_train = np.zeros(len(self.train_data))
        xgb_adj_train[valid_mask.values] = self._xgb.predict(feats_train[valid_mask])
        ensemble_train = yhat_train_prophet + xgb_adj_train

        self.pred_train = pd.DataFrame(
            {
                "ds": self.train_data["ds"].values,
                "yhat_prophet": yhat_train_prophet,
                "yhat_ensemble": ensemble_train,
            }
        )

        # Prophet + XGBoost sobre test
        if not self.test_data.empty:
            prophet_test = self._prophet.predict(self.test_data[["ds"]])
            yhat_test_prophet = prophet_test["yhat"].values

            full_y = pd.concat([self.train_data["y"], self.test_data["y"]], ignore_index=True)
            full_dates = pd.concat(
                [self.train_data["ds"], self.test_data["ds"]], ignore_index=True
            )
            feats_full = _construir_features_xgb(full_y, full_dates)
            feats_test = feats_full.iloc[len(self.train_data) :]
            feats_test_valid = feats_test.fillna(0)

            xgb_adj_test = self._xgb.predict(feats_test_valid)
            ensemble_test = yhat_test_prophet + xgb_adj_test

            self.pred_test = pd.DataFrame(
                {
                    "ds": self.test_data["ds"].values,
                    "yhat_prophet": yhat_test_prophet,
                    "yhat_ensemble": ensemble_test,
                }
            )

    def _calcular_metricas_test(self, nombre: str) -> dict[str, Any]:
        """Calcula metricas sobre el test set."""
        if self.test_data.empty or self.pred_test.empty:
            return {
                "modelo": nombre,
                "rmse": 0.0,
                "mae": 0.0,
                "smape": 0.0,
                "mase": None,
                "tiempo": self.tiempo_total,
            }

        y_true = self.test_data["y"].values
        y_train = self.train_data["y"].values
        y_pred = self.pred_test["yhat_ensemble"].values
        mase_val = mase(y_true, y_pred, y_train)

        return {
            "modelo": nombre,
            "rmse": rmse(y_true, y_pred),
            "mae": mae(y_true, y_pred),
            "smape": smape(y_true, y_pred),
            "mase": mase_val,
            "tiempo": self.tiempo_total,
        }
