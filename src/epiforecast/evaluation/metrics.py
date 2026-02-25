# src/epiforecast/evaluation/metrics.py
"""Forecasting evaluation metrics.

All functions accept numpy arrays and return scalar floats.
MASE additionally requires training data for naive baseline.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Root Mean Squared Error."""
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean Absolute Error."""
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def mape(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean Absolute Percentage Error (%).

    Zeros in y_true are excluded to avoid division by zero.
    Returns percentage (e.g., 6.11 not 0.0611).
    """
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def mase(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    y_train: ArrayLike,
    season: int = 52,
) -> float | None:
    """Mean Absolute Scaled Error vs seasonal naive (lag = season).

    MASE < 1: better than naive seasonal.
    MASE = 1: equal to naive seasonal.
    MASE > 1: worse than naive seasonal.

    Returns None if training series too short for seasonal naive.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    y_train = np.asarray(y_train, dtype=float)

    if len(y_train) <= season:
        return None

    mae_model = float(np.mean(np.abs(y_true - y_pred)))
    mae_naive = float(np.mean(np.abs(y_train[season:] - y_train[:-season])))

    if mae_naive == 0:
        return None

    return float(mae_model / mae_naive)
