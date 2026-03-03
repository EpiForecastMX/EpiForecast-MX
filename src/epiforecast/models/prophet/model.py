"""Prophet forecasting model implementation (SRP: model lifecycle only).

Handles: data preparation, training, prediction, serialization.
Delegates: cross-validation to cross_validator.py, HP tuning to tuner.py,
           backward-compatible API to prophet_compat.py,
           data prep helpers to data_prep.py.
"""

import logging
from pathlib import Path
import pickle
from typing import Any, cast

import numpy as np
import pandas as pd
from prophet import Prophet

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import register_model
from epiforecast.models.prophet.data_prep import (
    agrupa,
    apply_regional_params,
    build_holidays,
    build_seasonality_params,
    crea_train_test,
    eval_rapida,
    promedio_semanal,
)
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


@register_model("prophet")
class ProphetForecaster(ForecastModel):
    """Prophet-based time series forecaster (ForecastModel/LSP)."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str | None = None,
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        if not self.df.empty:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # Config values
        self.modelado_estados: bool = self._conf["padecimiento"]["modelado_estados"]
        self.entrena: bool = self._conf["padecimiento"]["entrena_modelo"]
        self.model_path: str = self._conf["paths"]["models"]
        self.model_save: str = self._conf["data"]["model_train"]

        # Rate normalization
        self.normalizar_tasa: bool = self._conf.get("normalizar_tasa", False)
        self.col_poblacion: str = self._conf.get("columna_poblacion", "Total")
        self.tasa_por: int = self._conf.get("tasa_por", 100000)
        self.log_transform: bool = self._conf.get("log_transform", False)
        self.poblacion_valor: float | None = None

        # Prophet model params
        self.param_model: dict = dict(self._conf["param_model"])
        apply_regional_params(self.param_model, self._conf, self.modelado_estados)

        # Seasonality params
        self.add_seasonality_params: dict = build_seasonality_params(
            self._conf, self.modelado_estados
        )

        # Atypical periods (holidays for Prophet)
        self.fechas_atipicas: pd.DataFrame = build_holidays(
            self._conf, self.entidad, self.padecimiento
        )

        # Data placeholders
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()

        # Train/test config
        self.FECHA_CORTE_ENTRENAMIENTO: str = self._conf["FECHA_CORTE_ENTRENAMIENTO"]

        # Internal model reference
        self._model: Prophet | None = None

    # ── Data Preparation ──────────────────────────────────────────────────────

    def agrupa(self) -> None:
        """Aggregate data by date, summing target column and optionally population."""
        self.serie = agrupa(self.df, self.sexo, self.normalizar_tasa, self.col_poblacion)

    def crea_train_test(self) -> None:
        """Create train/test split with rate normalization and log-transform."""
        self.serie, self.train_data, self.test_data, pob = crea_train_test(
            self.serie,
            self.sexo,
            self.normalizar_tasa,
            self.col_poblacion,
            self.log_transform,
            self.tasa_por,
            self.FECHA_CORTE_ENTRENAMIENTO,
        )
        if pob is not None:
            self.poblacion_valor = pob

    def promedio_semanal(self) -> float:
        """Return weekly average of original count (before transforms)."""
        return promedio_semanal(self.train_data)

    # ── ForecastModel Interface ───────────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame, parametros: dict | None = None) -> None:
        """Train Prophet model on provided data."""
        parametros = parametros or {}
        self._model = self._create_prophet(**parametros)

        try:
            np.random.seed(RANDOM_SEED)
            self._model.fit(train_data)
        except (RuntimeError, ValueError) as e:
            logger.warning("L-BFGS fall\u00f3, reintentando con cp=0.05: {}", e)
            fallback_params = {**parametros, "changepoint_prior_scale": 0.05}
            self._model = self._create_prophet(**fallback_params)
            np.random.seed(RANDOM_SEED)
            self._model.fit(train_data)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate predictions for given horizon (weeks)."""
        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        future = self._model.make_future_dataframe(periods=horizon, freq="W-MON")
        forecast = self._model.predict(future)
        cols = ["ds", "yhat", "yhat_lower", "yhat_upper"]
        out = forecast[cols].copy()

        if self.log_transform:
            for col in ["yhat", "yhat_lower", "yhat_upper"]:
                out[col] = np.expm1(out[col])
            logger.debug("Inversa de log-transform aplicada")

        if self.normalizar_tasa and self.poblacion_valor:
            out["yhat_tasa"] = out["yhat"]
            for col in ["yhat", "yhat_lower", "yhat_upper"]:
                out[col] = out[col] * self.poblacion_valor / self.tasa_por
            logger.debug(
                "Desnormalizaci\u00f3n de tasa aplicada (pob={:,.0f})", self.poblacion_valor
            )

        return out  # type: ignore[no-any-return]

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation. Delegates to ProphetCrossValidator."""
        from epiforecast.models.prophet.cross_validator import ProphetCrossValidator

        cv = ProphetCrossValidator(self)
        best_params, best_metrics = cv.run()
        return best_metrics

    def save(self, path: Path) -> None:
        """Serialize trained model to pickle file."""
        from epiforecast.utils.model_metadata import build_model_metadata

        if self._model is None:
            raise RuntimeError("No model to save. Call fit() first.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self._model, "_metadata": build_model_metadata()}
        with path.open("wb") as f:
            pickle.dump(payload, f)
        logger.debug("Modelo guardado: {}", path)

    def load(self, path: Path) -> None:
        """Load model from pickle file and population from sidecar CSV."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301
        # Nuevo formato: dict con "model" + "_metadata"; legacy: Prophet object directo
        if isinstance(payload, dict) and "model" in payload:
            self._model = payload["model"]
        else:
            self._model = payload
        logger.debug("Modelo cargado: {}", path)

        csv_path = path.with_suffix(".csv")
        if self.normalizar_tasa and csv_path.exists():
            train_csv = pd.read_csv(csv_path, nrows=1)
            col_pob = self.col_poblacion if self.col_poblacion in train_csv.columns else "Total"
            if col_pob in train_csv.columns:
                self.poblacion_valor = float(train_csv[col_pob].iloc[0])
                logger.debug("Poblaci\u00f3n cargada desde sidecar: {:,.0f}", self.poblacion_valor)

    def get_params(self) -> dict[str, Any]:
        """Return current model parameters."""
        return {
            "param_model": self.param_model,
            "add_seasonality": self.add_seasonality_params,
            "normalizar_tasa": self.normalizar_tasa,
            "log_transform": self.log_transform,
            "tasa_por": self.tasa_por,
        }

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[Prophet, dict, dict]:
        """Full pipeline: prepare data -> cross-validate -> train final model."""
        self.agrupa()
        self.crea_train_test()

        umbral = self._conf.get("umbral_minimo_semanal", 0)
        promedio = self.promedio_semanal()
        es_insuficiente = umbral and promedio < umbral

        if es_insuficiente:
            from epiforecast.models.prophet.prophet_compat import get_param_grid

            best_params = {k: v[0] for k, v in get_param_grid(self).items()}
            best_metrics: dict[str, Any] = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
            }
            confianza = "insuficiente"
            logger.debug(
                "Baja confianza: skip CV, params default | {:.2f} casos/sem | {} | {} | {}",
                promedio,
                self.padecimiento,
                self.entidad or "Nacional",
                self.sexo,
            )
        else:
            from epiforecast.models.prophet.tuner import ProphetTuner

            tuner = ProphetTuner(self)
            best_params, best_metrics = tuner.run()
            best_metrics = cast(dict[str, Any], best_metrics)
            confianza = "normal"

        self.fit(self.serie, best_params)

        if es_insuficiente:
            eval_metrics = eval_rapida(
                self._model,
                self.test_data,
                self.train_data,
                self.normalizar_tasa,
                self.poblacion_valor,
                self.log_transform,
                self.tasa_por,
                self.entidad,
                self.sexo,
            )
            best_metrics.update(eval_metrics)

        best_metrics["confianza"] = confianza
        best_metrics["promedio_semanal"] = promedio

        # Metricas in-sample (train) para deteccion de overfitting/leakage
        if self._model is not None and not self.train_data.empty:
            try:
                fc_train = self._model.predict(self.train_data[["ds"]])
                yhat_tr = fc_train["yhat"].to_numpy(dtype=float)
                y_tr = self.train_data["y"].to_numpy(dtype=float)
                if self.log_transform:
                    yhat_tr = np.expm1(yhat_tr)
                    y_tr = np.expm1(y_tr)
                train_m = compute_forecast_metrics(y_tr, yhat_tr, y_tr)
                best_metrics["rmse_train"] = train_m.get("rmse")
                best_metrics["smape_train"] = train_m.get("smape")
            except (ValueError, KeyError) as e:
                logger.warning("No se pudieron calcular metricas train (Prophet): {}", e)

        return self._model, best_metrics, best_params

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _create_prophet(self, **hp_overrides) -> Prophet:
        """Create a Prophet instance with configured params + HP overrides."""
        model = Prophet(holidays=self.fechas_atipicas, **self.param_model, **hp_overrides)
        model.add_seasonality(**self.add_seasonality_params)
        return model
