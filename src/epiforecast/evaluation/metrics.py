"""Forecasting evaluation metrics (MAPE, RMSE, MAE, MDAPE, MASE)."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Error."""
    return float(mean_absolute_error(y_true, y_pred))


def mape(y_true: np.ndarray, y_pred: np.ndarray, cap: float = 999.0) -> float:
    """Mean Absolute Percentage Error (capped)."""
    return float(min(mean_absolute_percentage_error(y_true, y_pred) * 100, cap))


def mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
    seasonal_period: int = 52,
) -> float | None:
    """Mean Absolute Scaled Error (vs seasonal naive baseline).

    MASE < 1 means model beats the naive seasonal baseline (lag=seasonal_period).
    Returns None if training data is too short for seasonal naive.
    """
    if len(y_train) <= seasonal_period:
        return None
    mae_model = mean_absolute_error(y_true, y_pred)
    mae_naive = float(np.mean(np.abs(y_train[seasonal_period:] - y_train[:-seasonal_period])))
    if mae_naive == 0:
        return None
    return float(mae_model / mae_naive)


def compute_all(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray | None = None,
) -> dict[str, float | None]:
    """Compute all metrics at once."""
    result = {
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "mape": mape(y_true, y_pred),
    }
    if y_train is not None:
        result["mase"] = mase(y_true, y_pred, y_train)
    return result
