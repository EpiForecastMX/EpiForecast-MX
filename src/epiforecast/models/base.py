"""Abstract base class for all forecasting models (LSP + OCP)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd


class ForecastModel(ABC):
    """Base interface for all forecasting models.

    Implementing classes: ProphetForecaster, DeepARForecaster, etc.
    All are interchangeable via this interface (Liskov Substitution).
    """

    @abstractmethod
    def fit(self, train_data: pd.DataFrame) -> None:
        """Train the model on the provided data."""

    @abstractmethod
    def predict(self, horizon: int) -> pd.DataFrame:
        """Generate predictions for the given horizon.

        Returns DataFrame with columns: ds, yhat, yhat_lower, yhat_upper.
        """

    @abstractmethod
    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation and return metrics dict.

        Expected keys: rmse, mae, mape, mase.
        """

    @abstractmethod
    def save(self, path: Path) -> None:
        """Serialize model to disk."""

    @abstractmethod
    def load(self, path: Path) -> None:
        """Load model from disk."""

    @abstractmethod
    def get_params(self) -> dict[str, Any]:
        """Return current model parameters."""

    @property
    def ultimo_ds_ajustado(self) -> "pd.Timestamp | None":
        """Última fecha que consumió el ajuste final del modelo, o ``None`` si no hay serie.

        Los cuatro motores de producción terminan su ``run()`` reajustando con ``self.serie``
        completa, así que la última fecha de esa serie es la que vio el ajuste persistido. Es el
        dato que permite marcar cada fila de pronóstico como ajuste o como futuro, y calcular su
        adelanto: sin él, ``predict`` devuelve ambos tramos mezclados y sin marcador.

        No debe confundirse con el sidecar guardado junto al modelo: ese conserva la serie
        completa aunque el ajuste haya consumido menos, que es como se llegó a creer que
        Ensemble y Stacking estaban ajustados hasta enero de 2026.
        """
        serie = getattr(self, "serie", None)
        if (
            serie is None
            or getattr(serie, "empty", True)
            or "ds" not in getattr(serie, "columns", [])
        ):
            return None
        return pd.Timestamp(serie["ds"].max())

    @property
    def intervalo_nominal(self) -> float | None:
        """Nivel nominal del intervalo propio del motor, o ``None`` si no produce intervalo.

        Por omisión un motor **no** tiene intervalo. Declararlo es responsabilidad de quien lo
        produce: emitir ``lower = upper = yhat`` no es un intervalo angosto, es su ausencia.
        """
        return None

    @property
    def intervalo_metodo(self) -> str | None:
        """Cómo se construye ese intervalo, para que viaje junto al dato."""
        return None

    @abstractmethod
    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        """Execute the full model pipeline: prepare data, cross-validate, train.

        Returns:
            (model_object, metrics_dict, params_dict)
        """
