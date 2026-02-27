# src/epiforecast/models/deepar/model.py
"""DeepAR forecasting model implementation (AWS SageMaker / GluonTS).

Refactored following technical review:
- Added Scaling, Context Length, and Output Distribution considerations.
- Improved dummy logic to simulate Negative Binomial noise and annual seasonality.
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger


@register_model("deepar")
class DeepARForecaster(ForecastModel):
    """DeepAR-based time series forecaster using AWS SageMaker or GluonTS."""

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

        # DeepAR Technical Hyperparameters (from config or defaults)
        self.deepar_conf = self._conf.get("deepar", {})
        self.epochs = self.deepar_conf.get("epochs", 100)
        self.context_length = self.deepar_conf.get("context_length", 52)
        self.num_layers = self.deepar_conf.get("num_layers", 2)
        self.learning_rate = self.deepar_conf.get("learning_rate", 1e-3)
        self.scaling = self.deepar_conf.get("scaling", True)
        self.distr_output = self.deepar_conf.get("distr_output", "negative-binomial")

        self._model: Any = None
        self.serie: pd.DataFrame = pd.DataFrame()

        if not self.df.empty and "Fecha" in self.df.columns:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])

    def fit(self, train_data: pd.DataFrame) -> None:
        """Skeleton for SageMaker/GluonTS training."""
        logger.info(
            "DeepAR fit() | Epochs: {} | Context: {} | Scaling: {} | Distr: {}",
            self.epochs,
            self.context_length,
            self.scaling,
            self.distr_output,
        )
        # Here we would initialize the Estimator and call .train()
        pass

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate high-fidelity dummy predictions simulating DeepAR performance."""
        logger.info(
            "DeepAR predict() | Simulating variability with {} distribution", self.distr_output
        )

        # Determine forecast start
        start_date = pd.Timestamp("2026-02-09")
        last_value = 2300.0
        if not self.serie.empty:
            start_date = self.serie["ds"].max() + pd.Timedelta(weeks=1)
            last_value = float(self.serie["y"].iloc[-1])

        dates = pd.date_range(start=start_date, periods=horizon, freq="W-MON")

        # 1. Seasonality (Annual cycle)
        # DeepAR learns this through context_length and dynamic features
        t = np.arange(horizon)
        seasonality = 0.15 * np.sin(2 * np.pi * t / 52)

        # 2. Trend (Subtle)
        trend = np.linspace(0, 0.03, horizon)

        # 3. Variability (Simulating Negative Binomial/Student-t)
        # Instead of Gaussian noise, we use Gamma-Poisson mixture vibe or simply higher variance
        np.random.seed(42)
        noise = np.random.gamma(shape=2.0, scale=0.05, size=horizon) - 0.1

        multiplier = 1 + trend + seasonality + noise
        yhat_future = last_value * multiplier

        # Confidence intervals (wider for Negative Binomial simulation)
        df_future = pd.DataFrame(
            {
                "ds": dates,
                "yhat": yhat_future,
                "yhat_lower": yhat_future * (0.75 - 0.05 * np.sqrt(t / horizon)),
                "yhat_upper": yhat_future * (1.25 + 0.05 * np.sqrt(t / horizon)),
            }
        )

        if not self.serie.empty:
            df_history = self.serie.copy()
            df_history = df_history.rename(columns={"y": "yhat"})
            df_history["yhat_lower"] = df_history["yhat"]
            df_history["yhat_upper"] = df_history["yhat"]
            return pd.concat([df_history, df_history.tail(0), df_future], ignore_index=True)

        return df_future

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        return {"rmse": 0.0, "mae": 0.0, "mape": 0.0, "mase": 0.0}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        import pickle

        with path.open("wb") as f:
            pickle.dump({"config": self.get_params()}, f)

    def load(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])

    def get_params(self) -> dict[str, Any]:
        return {
            "epochs": self.epochs,
            "context_length": self.context_length,
            "num_layers": self.num_layers,
            "learning_rate": self.learning_rate,
            "scaling": self.scaling,
            "distr_output": self.distr_output,
        }

    def run(self) -> tuple[Any, dict, dict]:
        logger.info("DeepAR run() | {}-{}", self.entidad, self.padecimiento)

        if not self.df.empty and self.sexo and self.sexo in self.df.columns:
            self.serie = self.df.groupby("Fecha")[self.sexo].sum().reset_index()
            self.serie = self.serie.rename(columns={"Fecha": "ds", self.sexo: "y"})
            self.serie = self.serie.sort_values("ds")
            # All data available for the sidecar

        metrics = {
            "rmse": 0.0,
            "mae": 0.0,
            "mape": 0.0,
            "mase": 0.0,
            "confianza": "normal",
            "promedio_semanal": self.serie["y"].mean() if not self.serie.empty else 0,
        }

        self.fit(pd.DataFrame())
        return None, metrics, self.get_params()
