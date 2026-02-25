# src/epiforecast/models/prophet/model.py
"""Prophet forecasting model implementation (SRP: model lifecycle only).

Handles: data preparation, training, prediction, serialization.
Delegates: cross-validation to cross_validator.py, HP tuning to tuner.py.
"""

import logging
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd
from prophet import Prophet

from epiforecast.models.base import ForecastModel
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


class ProphetForecaster(ForecastModel):
    """Prophet-based time series forecaster.

    Implements ForecastModel interface (LSP). Can be swapped with
    DeepARForecaster, etc. via ModelFactory (OCP).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        sexo: str | None = None,
        entidad: str | None = None,
        padecimiento: str | None = None,
    ):
        self.df = df.copy()
        self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # Config values
        self.modelado_estados: bool = conf["padecimiento"]["modelado_estados"]
        self.entrena: bool = conf["padecimiento"]["entrena_modelo"]
        self.model_path: str = conf["paths"]["models"]
        self.model_save: str = conf["data"]["model_train"]

        # Rate normalization
        self.normalizar_tasa: bool = conf.get("normalizar_tasa", False)
        self.col_poblacion: str = conf.get("columna_poblacion", "Total")
        self.tasa_por: int = conf.get("tasa_por", 100000)
        self.log_transform: bool = conf.get("log_transform", False)
        self.poblacion_valor: float | None = None

        # Prophet model params
        self.param_model: dict = dict(conf["param_model"])
        self._apply_regional_params()

        # Seasonality params
        self.add_seasonality_params: dict = self._build_seasonality_params()

        # Atypical periods (holidays for Prophet)
        self.fechas_atipicas: pd.DataFrame = self._build_holidays()

        # Data placeholders
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()

        # Train/test config
        self.FECHA_CORTE_ENTRENAMIENTO: str = conf["FECHA_CORTE_ENTRENAMIENTO"]

        # Internal model reference
        self._model: Prophet | None = None

    # ── Data Preparation ──────────────────────────────────────────────────────

    def agrupa(self) -> None:
        """Aggregate data by date, summing target column and optionally population."""
        agg_dict = {self.sexo: "sum"}
        if self.normalizar_tasa and self.col_poblacion in self.df.columns:
            agg_dict[self.col_poblacion] = "sum"
        self.serie = self.df.groupby("Fecha").agg(agg_dict)

    def crea_train_test(self) -> None:
        """Create train/test split with rate normalization and log-transform."""
        self.serie = self.serie.rename_axis("ds").reset_index()

        if self.normalizar_tasa and self.col_poblacion in self.serie.columns:
            self.poblacion_valor = self.serie[self.col_poblacion].iloc[0]
            self.serie["y_original"] = self.serie[self.sexo]
            self.serie["y"] = (self.serie[self.sexo] / self.poblacion_valor) * self.tasa_por  # type: ignore[operator]
            self.serie = self.serie.drop(columns=[self.sexo])
            logger.info(
                "Normalizado a tasa por {:,.0f} hab. (población: {:,.0f})",
                self.tasa_por,
                self.poblacion_valor,
            )
        else:
            self.serie = self.serie.rename(columns={self.sexo: "y"})

        if self.log_transform:
            self.serie["y"] = np.log1p(self.serie["y"])
            logger.info("Log-transform aplicado: y = log(1 + y)")

        self.train_data = self.serie[self.serie["ds"] < self.FECHA_CORTE_ENTRENAMIENTO]
        self.test_data = self.serie[self.serie["ds"] >= self.FECHA_CORTE_ENTRENAMIENTO]

        logger.info(
            "Train: {} semanas (hasta {})",
            len(self.train_data),
            self.train_data["ds"].max().date(),
        )
        logger.info(
            "Test: {} semanas (desde {})",
            len(self.test_data),
            self.test_data["ds"].min().date(),
        )

    def promedio_semanal(self) -> float:
        """Return weekly average of original count (before transforms)."""
        if "y_original" in self.train_data.columns:
            return float(self.train_data["y_original"].mean())
        return float(self.train_data["y"].mean())

    # ── ForecastModel Interface ───────────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame, parametros: dict | None = None) -> None:
        """Train Prophet model on provided data.

        Args:
            train_data: DataFrame with 'ds' and 'y' columns.
            parametros: HP dict (seasonality_mode, changepoint_prior_scale, etc.)
        """
        parametros = parametros or {}
        self._model = self._create_prophet(**parametros)

        try:
            self._model.fit(train_data)
        except Exception as e:
            logger.warning("L-BFGS falló, reintentando con cp=0.05: {}", e)
            fallback_params = {**parametros, "changepoint_prior_scale": 0.05}
            self._model = self._create_prophet(**fallback_params)
            self._model.fit(train_data)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate predictions for given horizon (weeks).

        Returns DataFrame with: ds, yhat, yhat_lower, yhat_upper.
        """
        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        future = self._model.make_future_dataframe(periods=horizon, freq="W-MON")
        forecast = self._model.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]  # type: ignore[no-any-return]

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation. Delegates to ProphetCrossValidator."""
        from epiforecast.models.prophet.cross_validator import ProphetCrossValidator

        cv = ProphetCrossValidator(self)
        best_params, best_metrics = cv.run()
        return best_metrics

    def save(self, path: Path) -> None:
        """Serialize trained model to pickle file."""
        if self._model is None:
            raise RuntimeError("No model to save. Call fit() first.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(self._model, f)
        logger.info("Modelo guardado: {}", path)

    def load(self, path: Path) -> None:
        """Load model from pickle file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            self._model = pickle.load(f)
        logger.info("Modelo cargado: {}", path)

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
        """Full pipeline: prepare data → cross-validate → train final model.

        Returns:
            (trained_model, best_metrics, best_params)
        """
        self.agrupa()
        self.crea_train_test()

        from epiforecast.models.prophet.tuner import ProphetTuner

        tuner = ProphetTuner(self)
        best_params, best_metrics = tuner.run()

        self.fit(self.serie, best_params)

        return self._model, best_metrics, best_params

    # ── Backward-compatible API (SerieTiempoProphet alias in scripts/) ────────

    @property
    def param_grid(self) -> dict:
        """HP grid for this condition. Delegates to ProphetTuner."""
        from epiforecast.models.prophet.tuner import ProphetTuner

        return ProphetTuner(self).param_grid

    def train(self, parametros: dict) -> Prophet:
        """Train final model on full series with given HP dict.

        Called by scripts/entrena.py after prophet_cross_val().
        Trains on self.serie (full data, not just train split) and
        returns the fitted Prophet object for pickling.
        """
        self.fit(self.serie, parametros)
        return self._model  # type: ignore[return-value]

    def prophet_cross_val(self) -> tuple[dict, dict]:
        """Run HP search and return (best_params, best_metrics).

        Delegates to ProphetTuner.run().
        """
        from epiforecast.models.prophet.tuner import ProphetTuner

        return ProphetTuner(self).run()

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _create_prophet(self, **hp_overrides) -> Prophet:
        """Create a Prophet instance with configured params + HP overrides."""
        model = Prophet(
            holidays=self.fechas_atipicas,
            **self.param_model,
            **hp_overrides,
        )
        model.add_seasonality(**self.add_seasonality_params)
        return model

    def _apply_regional_params(self) -> None:
        """Apply regional overrides for state-level models (shorter series)."""
        n_cp_regional = conf.get("n_changepoints_regional", None)
        if self.modelado_estados and n_cp_regional is not None:
            self.param_model["n_changepoints"] = n_cp_regional
            logger.debug("n_changepoints_regional={} aplicado", n_cp_regional)

    def _build_seasonality_params(self) -> dict:
        """Build seasonality params, applying regional fourier_order if needed."""
        raw = dict(conf["add_seasonality"])
        fourier_regional = raw.pop("fourier_order_regional", None)
        if self.modelado_estados and fourier_regional is not None:
            raw["fourier_order"] = fourier_regional
            logger.debug("fourier_order_regional={} aplicado", fourier_regional)
        return raw

    def _build_holidays(self) -> pd.DataFrame:
        """Build holidays DataFrame from atypical periods + regime changes."""
        periodos = conf["peridos_atipicos"]
        holidays = pd.DataFrame(periodos)
        holidays["ds"] = pd.to_datetime(holidays["ds"])

        # Add entity-specific regime changes
        cambios = conf.get("cambios_regimen", [])
        if cambios and self.entidad:
            filtrados = [
                c
                for c in cambios
                if c.get("entidad") == self.entidad
                and (not c.get("padecimiento") or c.get("padecimiento") == self.padecimiento)
            ]
            if filtrados:
                df_cambios = pd.DataFrame(filtrados)
                df_cambios["ds"] = pd.to_datetime(df_cambios["ds"])
                cols = ["holiday", "ds", "lower_window", "upper_window"]
                holidays = pd.concat([holidays, df_cambios[cols]], ignore_index=True)
                logger.info(
                    "Cambios de régimen para {}: {}",
                    self.entidad,
                    [c["holiday"] for c in filtrados],
                )

        return holidays
