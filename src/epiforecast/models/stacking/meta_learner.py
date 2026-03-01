"""Meta-learner para Stacking: OOF validation + Ridge(positive=True)."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from epiforecast.utils.config import logger


class StackingMetaLearner:
    """Aprende pesos optimos para expertos via expanding-window OOF validation."""

    def __init__(
        self,
        experts: list[Any],
        alpha: float = 1.0,
        n_folds: int = 4,
        min_train_weeks: int = 104,
    ):
        self._experts = experts
        self._alpha = alpha
        self._n_folds = n_folds
        self._min_train_weeks = min_train_weeks

    def _compute_oof_folds(
        self,
        train_data: pd.DataFrame,
        oof_cutoff: str,
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """Distribuye N cutoffs expanding-window entre (cutoff - 1.5 anos) y cutoff."""
        cutoff_ts = pd.Timestamp(oof_cutoff)
        earliest = cutoff_ts - pd.DateOffset(months=18)

        # Generar cutoffs equidistantes
        cutoff_range = pd.date_range(earliest, cutoff_ts, periods=self._n_folds + 1)
        # Tomar los puntos intermedios (excluir el primero que seria el inicio)
        fold_cutoffs = cutoff_range[1:]

        folds: list[tuple[pd.DataFrame, pd.DataFrame]] = []
        for fc in fold_cutoffs:
            fold_train = train_data[train_data["ds"] < fc].copy().reset_index(drop=True)
            fold_val = (
                train_data[(train_data["ds"] >= fc) & (train_data["ds"] < cutoff_ts)]
                .copy()
                .reset_index(drop=True)
            )
            # Ultimo fold: val incluye hasta el final del oof_cutoff
            if fc == fold_cutoffs[-1]:
                fold_val = train_data[train_data["ds"] >= fc].copy().reset_index(drop=True)

            if len(fold_train) < self._min_train_weeks or len(fold_val) < 4:
                continue
            folds.append((fold_train, fold_val))

        return folds

    def fit_oof(
        self,
        train_data: pd.DataFrame,
        oof_cutoff: str,
    ) -> tuple[np.ndarray, Ridge | None]:
        """Expanding-window OOF: multiples folds para pesos Ridge robustos.

        Returns:
            (weights, ridge_model) — coeficientes Ridge y modelo (None si fallback).
        """
        n_experts = len(self._experts)

        folds = self._compute_oof_folds(train_data, oof_cutoff)

        if not folds:
            logger.warning(
                "OOF: sin folds validos (min_train={}, n_folds={}), usando pesos iguales",
                self._min_train_weeks,
                self._n_folds,
            )
            return np.ones(n_experts) / n_experts, None

        all_preds: list[np.ndarray] = []
        all_y: list[np.ndarray] = []

        for fold_idx, (fold_train, fold_val) in enumerate(folds):
            fold_preds: list[np.ndarray] = []
            for expert in self._experts:
                expert_copy = copy.deepcopy(expert)
                expert_copy.fit(fold_train)
                pred = expert_copy.predict(fold_val[["ds"]])
                fold_preds.append(pred)

            x_fold = np.column_stack(fold_preds)
            all_preds.append(x_fold)
            all_y.append(fold_val["y"].values.astype(float))
            logger.debug(
                "  OOF fold {}/{}: train={}, val={} filas",
                fold_idx + 1,
                len(folds),
                len(fold_train),
                len(fold_val),
            )

        x_oof = np.vstack(all_preds)
        y_oof = np.concatenate(all_y)

        ridge = Ridge(positive=True, fit_intercept=False, alpha=self._alpha)
        ridge.fit(x_oof, y_oof)

        weights = ridge.coef_
        w_sum = weights.sum()
        if w_sum > 0:
            weights = weights / w_sum
        logger.debug(
            "  OOF Ridge: pesos = [{:.4f}, {:.4f}, {:.4f}] (alpha={}, {} filas OOF, {} folds)",
            weights[0],
            weights[1],
            weights[2],
            self._alpha,
            len(y_oof),
            len(folds),
        )
        return weights, ridge
