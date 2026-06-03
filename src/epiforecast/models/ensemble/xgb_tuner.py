"""XGBoost hyperparameter tuner with temporal cross-validation.

Grid search over XGBoost HPs using OOF Prophet residuals as target.
Each CV fold re-trains a Prophet temporal para obtener residuos realistas.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from epiforecast.constants import RANDOM_SEED
from epiforecast.models.ensemble.feature_builder import construir_features_xgb
from epiforecast.utils.config import logger

if TYPE_CHECKING:
    from prophet import Prophet


# Default grid (overridden by config)
_DEFAULT_GRID: dict[str, list[Any]] = {
    "max_depth": [3, 4, 5],
    "learning_rate": [0.01, 0.03, 0.05],
    "subsample": [0.7, 0.8],
    "min_child_weight": [5, 10],
}

_DEFAULT_CV_SPLITS = 4
_DEFAULT_CV_TEST_SIZE = 26
_DEFAULT_EARLY_STOPPING = 15
_DEFAULT_N_ESTIMATORS_MAX = 500


def _compute_oof_residuals_for_cv(
    prophet: Prophet,
    train_data: pd.DataFrame,
    tscv: TimeSeriesSplit,
    prophet_hp: dict[str, Any],
    yearly_period: float,
    yearly_fourier: int,
    holidays: pd.DataFrame,
) -> tuple[
    npt.NDArray[np.floating[Any]],
    npt.NDArray[np.floating[Any]],
    list[tuple[npt.NDArray[Any], npt.NDArray[Any]]],
]:
    """Calcula residuos OOF por fold: cada fold re-entrena Prophet temporal.

    Returns:
        (feats_clean, residuos_clean, fold_indices) donde fold_indices contiene
        los indices relativos a feats_clean/residuos_clean.
    """
    from prophet import Prophet as _Prophet

    y_reset = train_data["y"].reset_index(drop=True)
    ds_reset = train_data["ds"].reset_index(drop=True)
    feats_full = construir_features_xgb(y_reset, ds_reset)
    valid_mask = feats_full.notna().all(axis=1)

    all_feats: list[npt.NDArray[np.floating[Any]]] = []
    all_residuos: list[npt.NDArray[np.floating[Any]]] = []
    fold_splits: list[tuple[npt.NDArray[Any], npt.NDArray[Any]]] = []

    valid_indices = np.flatnonzero(valid_mask.to_numpy())

    offset = 0
    for train_idx, val_idx in tscv.split(feats_full[valid_mask].values):
        fold_train_data: pd.DataFrame = train_data.iloc[valid_indices[train_idx]].copy()
        fold_val_data: pd.DataFrame = train_data.iloc[valid_indices[val_idx]].copy()

        # Re-entrenar Prophet temporal para este fold
        m = _Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=holidays if not holidays.empty else None,
            **prophet_hp,
        )
        m.add_seasonality(name="yearly_custom", period=yearly_period, fourier_order=yearly_fourier)
        m.fit(fold_train_data[["ds", "y"]])

        prophet_pred = m.predict(fold_val_data[["ds"]])
        residuos_fold = fold_val_data["y"].values - prophet_pred["yhat"].values

        feats_fold = feats_full[valid_mask].values[val_idx]

        n_fold = len(val_idx)
        fold_train_rel = np.arange(offset, offset + len(train_idx))
        fold_val_rel = np.arange(offset + len(train_idx), offset + len(train_idx) + n_fold)

        all_feats.append(feats_full[valid_mask].values[train_idx])
        all_feats.append(feats_fold)
        # Residuos de train: usar Prophet temporal del fold (no el global)
        prophet_train_pred = m.predict(fold_train_data[["ds", "y"]])
        residuos_train_fold = fold_train_data["y"].values - prophet_train_pred["yhat"].values
        all_residuos.append(residuos_train_fold)
        all_residuos.append(residuos_fold)

        fold_splits.append((fold_train_rel, fold_val_rel))
        offset += len(train_idx) + n_fold

    return np.vstack(all_feats), np.concatenate(all_residuos), fold_splits


class EnsembleXGBTuner:
    """Grid search + CV temporal para XGBoost sobre residuos Prophet.

    Args:
        prophet: Modelo Prophet ya entrenado.
        train_data: DataFrame con columnas ``ds`` y ``y``.
        config: Dict de configuracion (OmegaConf o plain dict).
    """

    def __init__(
        self,
        prophet: Prophet,
        train_data: pd.DataFrame,
        config: dict[str, Any],
        padecimiento: str | None = None,
    ) -> None:
        self._prophet = prophet
        self._train_data = train_data
        self._conf = config
        self._padecimiento = padecimiento

        # Grid from config
        grid_cfg = config.get("param_grid_xgboost", _DEFAULT_GRID)
        self._param_grid: dict[str, list[Any]] = {k: list(v) for k, v in grid_cfg.items()}

        # CV settings
        self._n_splits: int = int(config.get("xgb_cv_splits", _DEFAULT_CV_SPLITS))
        self._test_size: int = int(config.get("xgb_cv_test_size", _DEFAULT_CV_TEST_SIZE))
        self._early_stopping: int = int(
            config.get("xgb_early_stopping_rounds", _DEFAULT_EARLY_STOPPING)
        )
        self._n_estimators_max: int = int(
            config.get("xgb_n_estimators_max", _DEFAULT_N_ESTIMATORS_MAX)
        )

        # Prophet HP (para re-entrenar en cada fold)
        pb = config.get("prophet_base", {})
        self._prophet_hp: dict[str, Any] = {
            "changepoint_prior_scale": pb.get("changepoint_prior_scale", 0.05),
            "seasonality_prior_scale": pb.get("seasonality_prior_scale", 0.1),
            "seasonality_mode": pb.get("seasonality_mode", "additive"),
        }
        yc = pb.get("yearly_custom", {})
        self._yearly_period: float = yc.get("period", 365.25)
        self._yearly_fourier: int = yc.get("fourier_order", 10)
        # Fixed HP from config (not in grid)
        xgb_cfg = config.get("xgboost", {})
        self._colsample_bytree: float = float(xgb_cfg.get("colsample_bytree", 0.7))
        self._reg_alpha: float = float(xgb_cfg.get("reg_alpha", 0.1))
        self._reg_lambda: float = float(xgb_cfg.get("reg_lambda", 1.0))

        self._holidays: pd.DataFrame = pd.DataFrame()
        periodos = config.get("peridos_atipicos", [])
        if periodos:
            from epiforecast.models.ensemble.feature_builder import construir_holidays

            self._holidays = construir_holidays(config, self._padecimiento)

    def run(self) -> tuple[dict[str, Any], float]:
        """Ejecuta grid search con CV temporal sobre residuos OOF.

        Returns:
            (best_params, best_cv_rmse) — Mejores HP y su RMSE promedio.
        """
        from xgboost import XGBRegressor

        # 1) Features para validar tamanio
        feats_check = construir_features_xgb(
            self._train_data["y"].reset_index(drop=True),
            self._train_data["ds"].reset_index(drop=True),
        )
        valid_mask = feats_check.notna().all(axis=1)
        n_samples = int(valid_mask.sum())

        # Ajustar test_size si es mayor que lo disponible
        effective_test = min(self._test_size, n_samples // (self._n_splits + 1))
        if effective_test < 4:
            logger.warning("Serie muy corta para CV temporal, usando HP por defecto")
            return {}, float("inf")

        tscv = TimeSeriesSplit(n_splits=self._n_splits, test_size=effective_test)

        # 2) Residuos OOF por fold (re-entrena Prophet por fold)
        feats_clean, residuos_clean, fold_splits = _compute_oof_residuals_for_cv(
            self._prophet,
            self._train_data,
            tscv,
            self._prophet_hp,
            self._yearly_period,
            self._yearly_fourier,
            self._holidays,
        )

        # Pesos por fold (mas reciente = mas peso, patron Prophet)
        raw_weights = np.arange(1, self._n_splits + 1, dtype=float)
        cv_weights = raw_weights / raw_weights.sum()

        # 3) Grid search
        param_names = list(self._param_grid.keys())
        param_values = list(self._param_grid.values())
        combos = list(itertools.product(*param_values))

        best_rmse = float("inf")
        best_params: dict[str, Any] = {}

        for combo in combos:
            hp = dict(zip(param_names, combo, strict=True))
            fold_rmses: list[float] = []

            for train_idx, val_idx in fold_splits:
                x_tr = feats_clean[train_idx]
                x_val = feats_clean[val_idx]
                y_tr = residuos_clean[train_idx]
                y_val = residuos_clean[val_idx]

                model = XGBRegressor(
                    **hp,
                    n_estimators=self._n_estimators_max,
                    colsample_bytree=self._colsample_bytree,
                    reg_alpha=self._reg_alpha,
                    reg_lambda=self._reg_lambda,
                    n_jobs=-1,
                    random_state=RANDOM_SEED,
                )
                model.fit(
                    x_tr,
                    y_tr,
                    eval_set=[(x_val, y_val)],
                    verbose=False,
                )
                y_pred = model.predict(x_val)
                rmse = float(np.sqrt(np.mean((y_val - y_pred) ** 2)))
                fold_rmses.append(rmse)

            # RMSE promedio ponderado
            weighted_rmse = float(np.average(fold_rmses, weights=cv_weights))

            if weighted_rmse < best_rmse:
                best_rmse = weighted_rmse
                best_params = hp

        n_combos = len(combos)
        logger.info(
            "  XGB Tuning: {} combos x {} folds | Mejor RMSE: {:.2f} | HP: {}",
            n_combos,
            self._n_splits,
            best_rmse,
            best_params,
        )

        return best_params, best_rmse
