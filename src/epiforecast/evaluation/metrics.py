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


def smape(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Symmetric Mean Absolute Percentage Error (%).

    SMAPE = 100/n * sum(2|y-ŷ| / (|y|+|ŷ|))

    Más robusto que MAPE cuando y_true tiene valores cercanos a cero
    (e.g., Alzheimer, Parkinson con pocos casos). Rango: [0, 200].
    Pares donde ambos son cero se excluyen.
    """
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom > 0
    if not mask.any():
        return 0.0
    return float(np.mean(2.0 * np.abs(y_true[mask] - y_pred[mask]) / denom[mask]) * 100)


def compute_forecast_metrics(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    y_train: ArrayLike,
    season: int = 52,
) -> dict[str, float | None]:
    """Compute standard forecast metrics (RMSE, MAE, MAPE, SMAPE, MASE).

    Convenience function that bundles all individual metrics into a single
    dict, used across Prophet CV, DeepAR CV, and eval_rapida pipelines.

    Returns:
        Dict with keys: rmse, mae, mape, smape, mase.
    """
    y_true_a = np.asarray(y_true, dtype=float)
    y_pred_a = np.asarray(y_pred, dtype=float)

    # Clean inf/nan before computing
    mask = np.isfinite(y_true_a) & np.isfinite(y_pred_a)
    if not mask.all():
        y_true_a, y_pred_a = y_true_a[mask], y_pred_a[mask]

    return {
        "rmse": rmse(y_true_a, y_pred_a),
        "mae": mae(y_true_a, y_pred_a),
        "mape": min(mape(y_true_a, y_pred_a), 999.0),
        "smape": smape(y_true_a, y_pred_a),
        "mase": mase(y_true_a, y_pred_a, y_train, season=season),
    }


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
