"""Out-of-fold residuals for Ensemble XGBoost training.

Generates OOF Prophet residuals via expanding-window CV so XGBoost
learns from realistic (not optimistically small) prediction errors.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.models.ensemble.feature_builder import construir_features_xgb
from epiforecast.utils.config import logger


def generate_oof_residuals(
    train_data: pd.DataFrame,
    prophet_hp: dict[str, Any],
    yearly_period: float,
    yearly_fourier: int,
    holidays: pd.DataFrame,
    n_folds: int = 3,
) -> tuple[pd.DataFrame, npt.NDArray[np.floating[Any]]]:
    """Genera residuos OOF via expanding-window CV con Prophet temporal.

    Args:
        train_data: DataFrame con columnas ds, y.
        prophet_hp: Hiperparametros de Prophet (changepoint_prior_scale, etc.).
        yearly_period: Periodo de estacionalidad anual.
        yearly_fourier: Orden Fourier de estacionalidad anual.
        holidays: DataFrame de holidays para Prophet.
        n_folds: Numero de folds expanding-window.

    Returns:
        (features_oof, residuos_oof) — concatenados de todos los folds.
    """
    from prophet import Prophet

    n = len(train_data)
    min_train = max(n // (n_folds + 1), 52)
    fold_size = (n - min_train) // n_folds

    if fold_size < 4:
        logger.warning("OOF residuos: datos insuficientes ({} filas, {} folds)", n, n_folds)
        return pd.DataFrame(), np.array([])

    all_feats: list[pd.DataFrame] = []
    all_residuos: list[npt.NDArray[np.floating[Any]]] = []

    for fold_idx in range(n_folds):
        train_end = min_train + fold_idx * fold_size
        val_end = train_end + fold_size if fold_idx < n_folds - 1 else n

        fold_train = train_data.iloc[:train_end].copy().reset_index(drop=True)
        fold_val = train_data.iloc[train_end:val_end].copy().reset_index(drop=True)

        if len(fold_val) < 4:
            continue

        # Prophet temporal (NO toca self._prophet)
        m = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=holidays if not holidays.empty else None,
            **prophet_hp,
        )
        m.add_seasonality(name="yearly_custom", period=yearly_period, fourier_order=yearly_fourier)
        m.fit(fold_train)

        prophet_pred = m.predict(fold_val[["ds"]])
        residuos = fold_val["y"].values - prophet_pred["yhat"].values

        # Features XGBoost usando historia del fold_train para lags
        y_full = pd.concat([fold_train["y"], fold_val["y"]], ignore_index=True)
        ds_full = pd.concat([fold_train["ds"], fold_val["ds"]], ignore_index=True)
        feats_full = construir_features_xgb(y_full, ds_full)
        feats_val = feats_full.iloc[len(fold_train) :].reset_index(drop=True)

        all_feats.append(feats_val)
        all_residuos.append(residuos)

        logger.debug(
            "  OOF residuos fold {}/{}: train={}, val={} filas",
            fold_idx + 1,
            n_folds,
            len(fold_train),
            len(fold_val),
        )

    if not all_feats:
        return pd.DataFrame(), np.array([])

    return pd.concat(all_feats, ignore_index=True), np.concatenate(all_residuos)
