# src/epiforecast/models/deepar/model.py
"""DeepAR forecasting model implementation (GluonTS + PyTorch, local CPU).

Real implementation using GluonTS DeepAREstimator with PyTorch backend.
All GluonTS/torch imports are lazy (inside methods) to avoid import-time
side effects and allow the module to load even without GluonTS installed.
"""

from __future__ import annotations

from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger


def _resolve_distr_output(name: str) -> Any:
    """Map a distribution name string to a GluonTS DistributionOutput instance."""
    from gluonts.torch.distributions import (
        NegativeBinomialOutput,
        NormalOutput,
        StudentTOutput,
    )

    distributions: dict[str, Any] = {
        "negative-binomial": NegativeBinomialOutput,
        "normal": NormalOutput,
        "student-t": StudentTOutput,
    }
    cls = distributions.get(name)
    if cls is None:
        raise ValueError(f"Distribución desconocida: '{name}'. Opciones: {list(distributions)}")
    return cls()


@register_model("deepar")
class DeepARForecaster(ForecastModel):
    """DeepAR-based time series forecaster using GluonTS + PyTorch (local CPU)."""

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
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # DeepAR hyperparameters (from config/models/deepar.yaml → deepar: key)
        self.deepar_conf: dict = self._conf.get("deepar", {})
        self.epochs: int = self.deepar_conf.get("epochs", 100)
        self.context_length: int = self.deepar_conf.get("context_length", 52)
        self.prediction_length: int = self.deepar_conf.get("prediction_length", 52)
        self.num_layers: int = self.deepar_conf.get("num_layers", 2)
        self.num_cells: int = self.deepar_conf.get("num_cells", 40)
        self.dropout_rate: float = self.deepar_conf.get("dropout_rate", 0.1)
        self.learning_rate: float = self.deepar_conf.get("learning_rate", 1e-3)
        self.batch_size: int = self.deepar_conf.get("batch_size", 32)
        self.scaling: bool = self.deepar_conf.get("scaling", True)
        self.distr_output: str = self.deepar_conf.get("distr_output", "negative-binomial")
        self.num_samples: int = self.deepar_conf.get("num_samples", 200)
        self.freq: str = self.deepar_conf.get("freq", "W-MON")

        # Train/test config
        self.FECHA_CORTE_ENTRENAMIENTO: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"
        )

        # GluonTS predictor (set after training)
        self._predictor: Any = None

        # Data placeholders
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()

        if not self.df.empty and "Fecha" in self.df.columns:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])

    # ── Data Preparation ──────────────────────────────────────────────────────

    def agrupa(self) -> None:
        """Aggregate data by date, summing target column."""
        col: str = self.sexo or "general"
        self.serie = self.df.groupby("Fecha")[col].sum().reset_index()
        self.serie = self.serie.rename(columns={"Fecha": "ds", col: "y"})
        self.serie = self.serie.sort_values("ds").reset_index(drop=True)

    def crea_train_test(self) -> None:
        """Split data by FECHA_CORTE_ENTRENAMIENTO."""
        self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        self.train_data = self.serie[
            self.serie["ds"] < self.FECHA_CORTE_ENTRENAMIENTO
        ].reset_index(drop=True)

    def promedio_semanal(self) -> float:
        """Return weekly average of counts."""
        return float(self.train_data["y"].mean()) if not self.train_data.empty else 0.0

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _build_dataset(self, df: pd.DataFrame) -> Any:
        """Convert a [ds, y] DataFrame to a GluonTS PandasDataset.

        Resamples to fill any gaps (missing weeks → 0) so the DatetimeIndex
        has a consistent frequency that GluonTS requires.
        """
        from gluonts.dataset.pandas import PandasDataset

        ts = df.set_index("ds")["y"].copy()
        ts.index = pd.DatetimeIndex(ts.index)
        # Fill gaps (missing weeks) with 0 and enforce freq
        ts = ts.resample(self.freq).sum()
        ts = ts.fillna(0)
        return PandasDataset.from_long_dataframe(
            pd.DataFrame({"target": ts, "item_id": 0}),
            target="target",
            item_id="item_id",
        )

    def _create_estimator(self, **overrides: Any) -> Any:
        """Create a GluonTS DeepAREstimator with configured hyperparameters."""
        from gluonts.torch.model.deepar import DeepAREstimator

        epochs = overrides.pop("epochs", self.epochs)
        context_length = overrides.pop("context_length", self.context_length)
        prediction_length = overrides.pop("prediction_length", self.prediction_length)

        # Compute reasonable num_batches_per_epoch
        train_len = max(len(self.train_data), len(self.serie))
        num_batches = max(1, train_len // self.batch_size)

        return DeepAREstimator(
            freq=self.freq,
            prediction_length=prediction_length,
            context_length=context_length,
            num_layers=overrides.pop("num_layers", self.num_layers),
            hidden_size=overrides.pop("num_cells", self.num_cells),
            dropout_rate=overrides.pop("dropout_rate", self.dropout_rate),
            lr=overrides.pop("learning_rate", self.learning_rate),
            batch_size=self.batch_size,
            scaling=overrides.pop("scaling", self.scaling),
            distr_output=_resolve_distr_output(overrides.pop("distr_output", self.distr_output)),
            num_batches_per_epoch=num_batches,
            trainer_kwargs={
                "max_epochs": epochs,
                "accelerator": "cpu",
                "enable_progress_bar": False,
            },
        )

    # ── ForecastModel Interface ───────────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame) -> None:
        """Train DeepAR model on provided data using GluonTS."""
        import torch

        logger.info(
            "DeepAR fit() | Epochs: {} | Context: {} | Layers: {} | Distr: {}",
            self.epochs,
            self.context_length,
            self.num_layers,
            self.distr_output,
        )

        # Fix seeds for reproducibility
        torch.manual_seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        dataset = self._build_dataset(train_data)
        estimator = self._create_estimator()
        self._predictor = estimator.train(dataset)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate predictions using the trained DeepAR predictor."""
        if self._predictor is None:
            raise RuntimeError("Modelo no entrenado. Llama a fit() primero.")

        # Use all available history as context
        context_data = self.serie if not self.serie.empty else self.train_data
        if context_data.empty:
            raise RuntimeError("No hay datos de contexto para generar predicciones.")

        dataset = self._build_dataset(context_data)

        # Generate probabilistic forecasts
        forecasts = list(self._predictor.predict(dataset, num_samples=self.num_samples))
        fc = forecasts[0]

        # Extract point forecast and confidence intervals
        yhat = fc.mean
        yhat_lower = fc.quantile(0.05)
        yhat_upper = fc.quantile(0.95)

        # Build future dates
        last_date = context_data["ds"].max()
        dates_future = pd.date_range(
            start=last_date + pd.Timedelta(weeks=1),
            periods=len(yhat),
            freq=self.freq,
        )

        df_future = pd.DataFrame(
            {
                "ds": dates_future,
                "yhat": yhat,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )

        # Prepend historical data (consistent with Prophet pattern)
        if not self.serie.empty:
            df_history = self.serie[["ds", "y"]].copy()
            df_history = df_history.rename(columns={"y": "yhat"})
            df_history["yhat_lower"] = df_history["yhat"]
            df_history["yhat_upper"] = df_history["yhat"]
            return pd.concat([df_history, df_future], ignore_index=True)

        return df_future

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation. Delegates to DeepARCrossValidator."""
        from epiforecast.models.deepar.cross_validator import DeepARCrossValidator

        cv = DeepARCrossValidator(self, config=self._conf)
        return cv.run()

    def save(self, path: Path) -> None:
        """Serialize predictor to disk as pickle."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "predictor": self._predictor,
            "config": self.get_params(),
            "freq": self.freq,
            "prediction_length": self.prediction_length,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)
        logger.debug("Modelo DeepAR guardado: {}", path)

    def load(self, path: Path) -> None:
        """Load predictor from pickle and sidecar CSV for historical series."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")

        with path.open("rb") as f:
            payload = pickle.load(f)

        # Backward-compatible: old stub format was {"config": {...}}
        if isinstance(payload, dict) and "predictor" in payload:
            self._predictor = payload["predictor"]
        elif isinstance(payload, dict):
            logger.warning("Formato de pickle antiguo (stub). _predictor = None")
            self._predictor = None
        else:
            self._predictor = payload

        # Load sidecar CSV for historical context (needed for predict)
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])

    def get_params(self) -> dict[str, Any]:
        """Return current model hyperparameters as flat dict."""
        return {
            "epochs": self.epochs,
            "context_length": self.context_length,
            "prediction_length": self.prediction_length,
            "num_layers": self.num_layers,
            "num_cells": self.num_cells,
            "dropout_rate": self.dropout_rate,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "scaling": self.scaling,
            "distr_output": self.distr_output,
        }

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[Any, dict, dict]:
        """Full pipeline: prepare data, cross-validate (optional), train final model.

        Returns:
            (predictor, metrics_dict, params_dict)
        """
        logger.info("DeepAR run() | {}-{}", self.entidad or "Nacional", self.padecimiento)

        if self.df.empty or not self.sexo or self.sexo not in self.df.columns:
            logger.warning("Sin datos para entrenar DeepAR")
            metrics: dict[str, Any] = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
                "confianza": "insuficiente",
                "promedio_semanal": 0,
            }
            return None, metrics, self.get_params()

        self.agrupa()
        self.crea_train_test()

        promedio = self.promedio_semanal()
        umbral = self._conf.get("umbral_minimo_semanal", 0)
        es_insuficiente = umbral and promedio < umbral

        if es_insuficiente:
            confianza = "insuficiente"
            best_metrics: dict[str, Any] = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
            }
            logger.debug(
                "Baja confianza: skip CV | {:.2f} casos/sem | {} | {} | {}",
                promedio,
                self.padecimiento,
                self.entidad or "Nacional",
                self.sexo,
            )
        else:
            confianza = "normal"
            best_metrics = self.cross_validate(self.train_data)

        # Train on full series
        self.fit(self.serie)

        best_metrics["confianza"] = confianza
        best_metrics["promedio_semanal"] = promedio

        return self._predictor, best_metrics, self.get_params()
