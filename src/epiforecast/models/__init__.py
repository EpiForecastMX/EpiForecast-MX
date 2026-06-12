"""Models package for EpiForecast-MX.

This package implements five forecasting engines (Prophet, DeepAR, Ensemble,
Stacking and NBGLM) following the Strategy and Factory patterns.
"""

from epiforecast.models.base import ForecastModel
from epiforecast.models.deepar.model import DeepARForecaster
from epiforecast.models.ensemble.model import EnsembleForecaster
from epiforecast.models.factory import create_model, list_models
from epiforecast.models.nbglm.model import NBGLMForecaster
from epiforecast.models.prophet.model import ProphetForecaster
from epiforecast.models.stacking.model import StackingForecaster

__all__ = [
    "ForecastModel",
    "create_model",
    "list_models",
    "ProphetForecaster",
    "DeepARForecaster",
    "EnsembleForecaster",
    "StackingForecaster",
    "NBGLMForecaster",
]
