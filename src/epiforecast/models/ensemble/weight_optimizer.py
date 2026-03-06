"""EnsembleWeightOptimizer: expanding-window OOF + Ridge para pesos paralelos.

Aprende pesos [w_prophet, w_xgb] via expanding-window cross-validation.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.linear_model import Ridge

from epiforecast.utils.config import logger


class ProphetBuilder(Protocol):
    """Callable that builds a fitted Prophet model from training data."""

    def __call__(self, train_df: pd.DataFrame) -> Any: ...


class XGBBuilder(Protocol):
    """Callable that builds a fitted XGBDirect model from training data."""

    def __call__(self, train_df: pd.DataFrame) -> Any: ...


class EnsembleWeightOptimizer:
    """Aprende pesos optimos para Prophet + XGBDirect via expanding-window OOF."""

    def __init__(
        self,
        alpha: float = 1.0,
        n_folds: int = 4,
        min_train_weeks: int = 104,
    ) -> None:
        self._alpha = alpha
        self._n_folds = n_folds
        self._min_train_weeks = min_train_weeks
        self._ridge: Ridge | None = None

    def fit_oof(
        self,
        train_data: pd.DataFrame,
        prophet_builder: ProphetBuilder,
        xgb_builder: XGBBuilder,
        oof_cutoff: str,
    ) -> npt.NDArray[np.floating[Any]]:
        """Expanding-window OOF para aprender pesos [w_prophet, w_xgb].

        Args:
            train_data: DataFrame con columnas ds, y.
            prophet_builder: Callable(train_df) -> fitted prophet que tiene .predict().
            xgb_builder: Callable(train_df) -> fitted XGBDirectForecaster.
            oof_cutoff: Fecha de corte para distribuir folds.

        Returns:
            weights: array [w_prophet, w_xgb] que suman 1.
        """
        cutoff_ts = pd.Timestamp(oof_cutoff)
        earliest = cutoff_ts - pd.DateOffset(months=18)

        cutoff_range = pd.date_range(earliest, cutoff_ts, periods=self._n_folds + 1)
        fold_cutoffs = cutoff_range[1:]

        all_preds_prophet: list[npt.NDArray[np.floating[Any]]] = []
        all_preds_xgb: list[npt.NDArray[np.floating[Any]]] = []
        all_y: list[npt.NDArray[np.floating[Any]]] = []

        for fold_idx, fc in enumerate(fold_cutoffs):
            fold_train = train_data[train_data["ds"] < fc].copy().reset_index(drop=True)
            if fc == fold_cutoffs[-1]:
                fold_val = train_data[train_data["ds"] >= fc].copy().reset_index(drop=True)
            else:
                fold_val = (
                    train_data[(train_data["ds"] >= fc) & (train_data["ds"] < cutoff_ts)]
                    .copy()
                    .reset_index(drop=True)
                )

            if len(fold_train) < self._min_train_weeks or len(fold_val) < 4:
                continue

            # Prophet temporal
            prophet_temp = prophet_builder(fold_train)
            pred_prophet = prophet_temp.predict(fold_val[["ds"]])["yhat"].values

            # XGBDirect temporal (recursivo: no usa y real del val)
            xgb_temp = xgb_builder(fold_train)
            pred_xgb = xgb_temp.predict_recursive(fold_train, fold_val["ds"].values)

            all_preds_prophet.append(pred_prophet)
            all_preds_xgb.append(pred_xgb)
            all_y.append(fold_val["y"].to_numpy(dtype=float))

            logger.debug(
                "  Parallel OOF fold {}/{}: train={}, val={}",
                fold_idx + 1,
                len(fold_cutoffs),
                len(fold_train),
                len(fold_val),
            )

        if not all_y:
            logger.warning("Parallel OOF: sin folds validos, pesos iguales [0.5, 0.5]")
            return np.array([0.5, 0.5])

        x_oof = np.column_stack(
            [
                np.concatenate(all_preds_prophet),
                np.concatenate(all_preds_xgb),
            ]
        )
        y_oof = np.concatenate(all_y)

        self._ridge = Ridge(positive=True, fit_intercept=False, alpha=self._alpha)
        self._ridge.fit(x_oof, y_oof)

        weights = self._ridge.coef_.copy()
        w_sum = weights.sum()
        weights = weights / w_sum if w_sum > 0 else np.array([0.5, 0.5])

        logger.debug(
            "  Parallel OOF Ridge: w_prophet={:.4f}, w_xgb={:.4f} (alpha={}, {} filas, {} folds)",
            weights[0],
            weights[1],
            self._alpha,
            len(y_oof),
            len(all_y),
        )
        return weights
