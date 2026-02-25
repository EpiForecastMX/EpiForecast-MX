# src/epiforecast/models/prophet/__init__.py
"""Prophet forecasting model package.

Split into 3 modules following SRP:
- model.py: ProphetForecaster (fit, predict, save, load)
- tuner.py: ProphetTuner (HP grid search + Newton protection)
- cross_validator.py: ProphetCrossValidator (temporal CV + MASE)
"""

from epiforecast.models.prophet.model import ProphetForecaster

__all__ = ["ProphetForecaster"]
