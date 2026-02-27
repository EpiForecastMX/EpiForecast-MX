# src/epiforecast/models/prediction.py
"""Model loader and predictor (Polymorphic via ModelFactory).

Delegates loading and prediction to the specific model implementation.
"""

from pathlib import Path

import pandas as pd

from epiforecast.models import create_model
from epiforecast.utils.config import conf


class ForecastModelLoader:
    """Unified model loader that works with any registered model type."""

    def __init__(self, periodo: int, model_path: Path, config: dict | None = None):
        """Inicializa el cargador de modelos.

        Args:
            periodo:    Horizonte de predicción en semanas.
            model_path: Ruta al archivo del modelo serializado.
            config:     Dict de configuración (default: conf global de YAML).
        """
        self._conf = config if config is not None else conf
        self.model_path = Path(model_path)
        self.periodo = periodo

        # Determinar modelo_activo de la configuración
        self.modelo_activo = self._conf.get("modelo_activo", "prophet")

        # Instanciar el forecaster correspondiente
        self.forecaster = create_model(self.modelo_activo, config=self._conf)

    def load(self) -> None:
        """Delegate loading to the forecaster implementation."""
        self.forecaster.load(self.model_path)

    def predict(self) -> pd.DataFrame:
        """Delegate prediction to the forecaster implementation."""
        return self.forecaster.predict(self.periodo)

    def run(self) -> pd.DataFrame:
        """Load model and generate predictions in one call."""
        self.load()
        return self.predict()
