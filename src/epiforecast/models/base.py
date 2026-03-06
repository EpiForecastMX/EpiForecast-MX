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

    @abstractmethod
    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        """Execute the full model pipeline: prepare data, cross-validate, train.

        Returns:
            (model_object, metrics_dict, params_dict)
        """
