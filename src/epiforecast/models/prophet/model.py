"""Prophet forecasting model implementation (SRP: model lifecycle only).

Handles: data preparation, training, prediction, serialization.
Delegates: cross-validation to cross_validator.py, HP tuning to tuner.py,
           backward-compatible API to prophet_compat.py,
           data prep helpers to data_prep.py.
"""

import logging
from pathlib import Path
import pickle
from typing import Any

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
from epiforecast.utils.cohorts import is_count_log_cohort, is_neuro
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
        config: dict[str, Any] | None = None,
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

        # Rate normalization: neuro modela tasa/100k; la cohorte de conteos-log no (la tasa
        # comprime la señal en log y colapsa el forecast). Ver utils.cohorts.
        self.normalizar_tasa: bool = self._conf.get(
            "normalizar_tasa", False
        ) and not is_count_log_cohort(self.padecimiento)
        self.col_poblacion: str = self._conf.get("columna_poblacion", "Total")
        self.tasa_por: int = self._conf.get("tasa_por", 100000)
        # log_transform: neuro y conteos-log (sin log la tendencia colapsa). Ver utils.cohorts.
        self.log_transform: bool = self._conf.get("log_transform", False) and (
            is_neuro(self.padecimiento) or is_count_log_cohort(self.padecimiento)
        )
        self.poblacion_valor: float | None = None

        # Regresor ENSO/El Niño (índice ONI): solo cohorte de conteos (Dengue). El ciclo
        # inter-anual del dengue sigue a El Niño, señal que NO está en los conteos recientes.
        # Cohort-gated: neuro nunca activa esto -> serie sin columna 'oni', add_regressor no
        # se llama, predicción byte-idéntica. Ver epiforecast.data.enso.
        self.enso_regressor: bool = bool(
            self._conf.get("enso_regressor", False)
        ) and is_count_log_cohort(self.padecimiento)
        self.enso_lag_weeks: int = int(self._conf.get("enso_lag_weeks", 16))
        self._train_max_ds: pd.Timestamp | None = None

        # Prophet model params
        self.param_model: dict[str, Any] = dict(self._conf["param_model"])
        apply_regional_params(self.param_model, self._conf, self.modelado_estados)

        # Seasonality params
        self.add_seasonality_params: dict[str, Any] = build_seasonality_params(
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
        self._train_max_ds = self.serie["ds"].max() if not self.serie.empty else None
        self._attach_enso()

    def _attach_enso(self) -> None:
        """Adjunta la columna 'oni' (rezagada) a serie/train/test si el regresor ENSO está
        activo (solo cohorte de conteos). El ONI histórico es observado (as_of=None)."""
        if not self.enso_regressor:
            return
        from epiforecast.data import enso

        for attr in ("serie", "train_data", "test_data"):
            frame = getattr(self, attr)
            if not frame.empty:
                frame = frame.copy()  # train/test son slices de serie -> evitar SettingWithCopy
                frame["oni"] = enso.oni_for_dates(frame["ds"], lag_weeks=self.enso_lag_weeks)
                setattr(self, attr, frame)

    def promedio_semanal(self) -> float:
        """Return weekly average of original count (before transforms)."""
        return promedio_semanal(self.train_data)

    # ── ForecastModel Interface ───────────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame, parametros: dict[str, Any] | None = None) -> None:
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
        if self.enso_regressor:
            # ONI del horizonte futuro: observado donde el rezago ya lo entrega +
            # persistencia amortiguada hacia neutral para la cola (estrategia desplegable).
            from epiforecast.data import enso

            future["oni"] = enso.oni_for_dates(
                future["ds"], lag_weeks=self.enso_lag_weeks, as_of=self._train_max_ds
            )
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

        return out

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
            "enso_regressor": self.enso_regressor,
            "tasa_por": self.tasa_por,
        }

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[Prophet, dict[str, Any], dict[str, Any]]:
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
                tr_cols = ["ds", "oni"] if self.enso_regressor else ["ds"]
                fc_train = self._model.predict(self.train_data[tr_cols])
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

    def _create_prophet(self, **hp_overrides: Any) -> Prophet:
        """Create a Prophet instance with configured params + HP overrides."""
        holidays = self.fechas_atipicas if not self.fechas_atipicas.empty else None
        model = Prophet(holidays=holidays, **self.param_model, **hp_overrides)
        model.add_seasonality(**self.add_seasonality_params)
        if self.enso_regressor:
            model.add_regressor("oni")
        return model
