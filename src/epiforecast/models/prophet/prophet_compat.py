"""Backward-compatible API for legacy scripts (extracted from ProphetForecaster — SRP).

Functions in this module wrap ProphetForecaster + ProphetTuner calls that
``scripts/entrena.py`` and similar consumers historically accessed as methods
on the forecaster instance.  Import from here instead::

    from epiforecast.models.prophet.prophet_compat import (
        get_param_grid,
        train_on_full_series,
        prophet_cross_val,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prophet import Prophet

    from epiforecast.models.prophet.model import ProphetForecaster


def get_param_grid(forecaster: ProphetForecaster) -> dict[str, Any]:
    """HP grid for the forecaster's condition. Delegates to ProphetTuner."""
    from epiforecast.models.prophet.tuner import ProphetTuner

    return ProphetTuner(forecaster).param_grid


def train_on_full_series(forecaster: ProphetForecaster, parametros: dict[str, Any]) -> Prophet:
    """Train final model on full series and return the fitted Prophet object.

    Equivalent to the old ``forecaster.train(parametros)`` method.
    """
    forecaster.fit(forecaster.serie, parametros)
    assert forecaster._model is not None  # set by fit() above
    return forecaster._model


def prophet_cross_val(forecaster: ProphetForecaster) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run HP search and return ``(best_params, best_metrics)``.

    Equivalent to the old ``forecaster.prophet_cross_val()`` method.
    """
    from epiforecast.models.prophet.tuner import ProphetTuner

    return ProphetTuner(forecaster).run()
