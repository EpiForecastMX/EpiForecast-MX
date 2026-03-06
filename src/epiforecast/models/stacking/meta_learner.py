"""Meta-learner para Stacking: OOF validation + Ridge/ElasticNet."""

from __future__ import annotations

import copy
import gc
from typing import Any
import warnings

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, Ridge

from epiforecast.utils.config import logger

# Umbral minimo de variabilidad en target OOF para que el meta-learner converja
_MIN_TARGET_STD: float = 1e-8


class StackingMetaLearner:
    """Aprende pesos optimos para expertos via expanding-window OOF validation."""

    def __init__(
        self,
        experts: list[Any],
        alpha: float = 1.0,
        n_folds: int = 4,
        min_train_weeks: int = 104,
        meta_type: str = "ridge",
        l1_ratio: float = 0.5,
        add_temporal_features: bool = False,
        max_iter: int = 10_000,
        tol: float = 1e-4,
    ):
        self._experts = experts
        self._alpha = alpha
        self._n_folds = n_folds
        self._min_train_weeks = min_train_weeks
        self._meta_type = meta_type
        self._l1_ratio = l1_ratio
        self._add_temporal_features = add_temporal_features
        self._max_iter = max_iter
        self._tol = tol

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

    @staticmethod
    def _clone_expert(expert: Any) -> Any:
        """Crea instancia fresca de un experto sin deepcopy (evita leaked semaphores)."""
        try:
            cls = type(expert)
            if hasattr(expert, "_holidays"):
                return cls(expert._config, expert._holidays)
            return cls(expert._config)
        except Exception:  # noqa: BLE001 — deliberate fallback pattern
            logger.debug("fresh_expert: fallback a deepcopy para {}", type(expert).__name__)
            return copy.deepcopy(expert)

    @staticmethod
    def _augment_with_temporal(
        x: npt.NDArray[np.floating[Any]], dates: pd.Series
    ) -> npt.NDArray[np.floating[Any]]:
        """Agrega sin_week y cos_week al stack de predicciones."""
        week_vals = dates.dt.isocalendar().week.astype(int).values
        sin_week = np.sin(2 * np.pi * week_vals / 52).reshape(-1, 1)
        cos_week = np.cos(2 * np.pi * week_vals / 52).reshape(-1, 1)
        return np.hstack([x, sin_week, cos_week])

    def fit_oof(
        self,
        train_data: pd.DataFrame,
        oof_cutoff: str,
    ) -> tuple[npt.NDArray[np.floating[Any]], Ridge | ElasticNet | None]:
        """Expanding-window OOF: multiples folds para pesos robustos.

        Returns:
            (weights, model) — coeficientes normalizados y modelo (None si fallback).
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

        all_preds: list[npt.NDArray[np.floating[Any]]] = []
        all_dates: list[pd.Series] = []
        all_y: list[npt.NDArray[np.floating[Any]]] = []

        for fold_idx, (fold_train, fold_val) in enumerate(folds):
            # Fix 3: descartar folds con target casi constante
            if np.std(fold_val["y"].to_numpy()) < _MIN_TARGET_STD:
                logger.debug(
                    "  OOF fold {}/{}: val casi constante (std={:.2e}), skip",
                    fold_idx + 1,
                    len(folds),
                    np.std(fold_val["y"].to_numpy()),
                )
                continue

            fold_preds: list[npt.NDArray[np.floating[Any]]] = []
            for expert in self._experts:
                fresh = self._clone_expert(expert)
                fresh.fit(fold_train)
                pred = fresh.predict(fold_val[["ds"]])
                fold_preds.append(pred)
                fresh._model = None
                del fresh
            gc.collect()

            x_fold = np.column_stack(fold_preds)
            all_preds.append(x_fold)
            all_dates.append(fold_val["ds"].reset_index(drop=True))
            all_y.append(fold_val["y"].to_numpy(dtype=float))
            logger.debug(
                "  OOF fold {}/{}: train={}, val={} filas",
                fold_idx + 1,
                len(folds),
                len(fold_train),
                len(fold_val),
            )

        if not all_preds:
            logger.warning(
                "OOF: todos los folds descartados (target constante), usando pesos iguales",
            )
            return np.ones(n_experts) / n_experts, None

        x_oof = np.vstack(all_preds)
        y_oof = np.concatenate(all_y)

        # Fix 1: guard de varianza minima antes de fit
        if np.std(y_oof) < _MIN_TARGET_STD:
            logger.warning(
                "  OOF target casi constante (std={:.2e}, {} filas), fallback a pesos iguales",
                np.std(y_oof),
                len(y_oof),
            )
            return np.ones(n_experts) / n_experts, None

        if self._add_temporal_features:
            dates_oof = pd.concat(all_dates, ignore_index=True)
            x_oof = self._augment_with_temporal(x_oof, dates_oof)

        # Fix 2: max_iter y tol explicitos
        model: Ridge | ElasticNet
        if self._meta_type == "elasticnet":
            model = ElasticNet(
                positive=True,
                fit_intercept=False,
                alpha=self._alpha,
                l1_ratio=self._l1_ratio,
                max_iter=self._max_iter,
                tol=self._tol,
            )
        else:
            model = Ridge(
                positive=True,
                fit_intercept=False,
                alpha=self._alpha,
                max_iter=self._max_iter,
                tol=self._tol,
            )

        # Fix 4: capturar ConvergenceWarning sin contaminar stdout
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            model.fit(x_oof, y_oof)

        for w in caught:
            if issubclass(w.category, ConvergenceWarning):
                logger.warning(
                    "  Meta-learner ConvergenceWarning: {} (alpha={}, {} filas OOF)",
                    str(w.message)[:100],
                    self._alpha,
                    len(y_oof),
                )

        # Normalizar solo los coeficientes de expertos (primeros n_experts)
        weights = model.coef_[:n_experts].copy()
        w_sum = weights.sum()
        if w_sum > 0:
            weights = weights / w_sum

        logger.debug(
            "  OOF {}: pesos = [{:.4f}, {:.4f}, {:.4f}] (alpha={}, {} filas OOF, {} folds)",
            self._meta_type,
            weights[0],
            weights[1],
            weights[2],
            self._alpha,
            len(y_oof),
            len(folds),
        )
        return weights, model
