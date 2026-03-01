"""Meta-learner para Stacking: OOF validation + Ridge(positive=True)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from epiforecast.utils.config import logger


class StackingMetaLearner:
    """Aprende pesos optimos para expertos via OOF validation."""

    def __init__(self, experts: list[Any], alpha: float = 1.0):
        self._experts = experts
        self._alpha = alpha

    def fit_oof(
        self,
        train_data: pd.DataFrame,
        oof_cutoff: str,
    ) -> tuple[np.ndarray, Ridge | None]:
        """OOF validation: train < oof_cutoff, predict oof_cutoff..end.

        Returns:
            (weights, ridge_model) — coeficientes Ridge y modelo (None si fallback).
        """
        cutoff_ts = pd.Timestamp(oof_cutoff)
        oof_train = train_data[train_data["ds"] < cutoff_ts].copy().reset_index(drop=True)
        oof_val = train_data[train_data["ds"] >= cutoff_ts].copy().reset_index(drop=True)

        n_experts = len(self._experts)

        if len(oof_val) < 4:
            logger.warning(
                "OOF: solo {} filas de validacion (< 4), usando pesos iguales",
                len(oof_val),
            )
            return np.ones(n_experts) / n_experts, None

        preds: list[np.ndarray] = []
        for expert in self._experts:
            expert.fit(oof_train)
            pred = expert.predict(oof_val[["ds"]])
            preds.append(pred)

        x_oof = np.column_stack(preds)
        y = oof_val["y"].values.astype(float)

        ridge = Ridge(positive=True, fit_intercept=False, alpha=self._alpha)
        ridge.fit(x_oof, y)

        weights = ridge.coef_
        logger.debug(
            "  OOF Ridge: pesos = [{:.4f}, {:.4f}, {:.4f}] (alpha={}, {} filas OOF)",
            weights[0],
            weights[1],
            weights[2],
            self._alpha,
            len(oof_val),
        )
        return weights, ridge
