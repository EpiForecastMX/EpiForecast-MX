# src/epiforecast/models/prediction.py
"""Model loader and predictor with inverse transforms (SRP: load + predict only).

Handles: loading .pkl models, reversing log-transform, desnormalizing rates to counts.
Does NOT handle: visualization (see visualization/forecast_plots.py).
"""

from pathlib import Path
import pickle

import numpy as np
import pandas as pd

from epiforecast.utils.config import conf


class ForecastModelLoader:
    """Load a serialized Prophet model and generate desnormalized predictions."""

    def __init__(self, periodo: int, model_path: Path):
        """Inicializa el cargador de modelos con horizonte y ruta del pickle.

        Args:
            periodo:    Horizonte de predicción en semanas.
            model_path: Ruta al archivo .pkl del modelo serializado.
        """
        self.model_path = Path(model_path)
        self.model = None
        self.periodo = periodo
        self.poblacion: float | None = None
        self.normalizar_tasa: bool = conf.get("normalizar_tasa", False)
        self.tasa_por: int = conf.get("tasa_por", 100000)
        self.log_transform: bool = conf.get("log_transform", False)

    def load(self) -> None:
        """Load model from .pkl and read population from sidecar CSV."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {self.model_path}")

        with self.model_path.open("rb") as f:
            self.model = pickle.load(f)

        # Read population from training CSV (sidecar of .pkl)
        csv_path = self.model_path.with_suffix(".csv")
        if self.normalizar_tasa and csv_path.exists():
            train_csv = pd.read_csv(csv_path, nrows=1)
            if "Total" in train_csv.columns:
                self.poblacion = train_csv["Total"].iloc[0]

    def predict(self) -> pd.DataFrame:
        """Generate predictions, reversing log-transform and rate normalization."""
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        future = self.model.make_future_dataframe(periods=self.periodo, freq="W-MON")
        forecast = self.model.predict(future)

        # Reverse log-transform: exp(yhat) - 1
        if self.log_transform:
            for col in ["yhat", "yhat_lower", "yhat_upper"]:
                forecast[col] = np.expm1(forecast[col])

        # Desnormalize rate to counts
        if self.normalizar_tasa and self.poblacion:
            forecast["yhat_tasa"] = forecast["yhat"]
            for col in ["yhat", "yhat_lower", "yhat_upper"]:
                forecast[col] = forecast[col] * self.poblacion / self.tasa_por

        return forecast

    def run(self) -> pd.DataFrame:
        """Load model and generate predictions in one call."""
        self.load()
        return self.predict()
