"""XGBoost hyperparameter tuner with temporal cross-validation.

Grid search over XGBoost HPs using Prophet residuals as target.
Prophet is NOT re-trained — only the residual correction is tuned.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from epiforecast.constants import RANDOM_SEED
from epiforecast.models.ensemble.helpers import construir_features_xgb
from epiforecast.utils.config import logger

if TYPE_CHECKING:
    from prophet import Prophet


# Default grid (overridden by config)
_DEFAULT_GRID: dict[str, list[Any]] = {
    "max_depth": [3, 4, 5, 6],
    "learning_rate": [0.01, 0.05, 0.1],
    "subsample": [0.7, 0.8, 0.9],
}

_DEFAULT_CV_SPLITS = 4
_DEFAULT_CV_TEST_SIZE = 26
_DEFAULT_EARLY_STOPPING = 15
_DEFAULT_N_ESTIMATORS_MAX = 500


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
    ) -> None:
        self._prophet = prophet
        self._train_data = train_data
        self._conf = config

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

    def run(self) -> tuple[dict[str, Any], float]:
        """Ejecuta grid search con CV temporal.

        Returns:
            (best_params, best_cv_rmse) — Mejores HP y su RMSE promedio.
        """
        from xgboost import XGBRegressor

        # 1) Residuos Prophet (una sola vez)
        prophet_pred = self._prophet.predict(self._train_data[["ds"]])
        residuos = self._train_data["y"].values - prophet_pred["yhat"].values

        # 2) Features XGBoost (una sola vez)
        feats = construir_features_xgb(
            self._train_data["y"].reset_index(drop=True),
            self._train_data["ds"].reset_index(drop=True),
        )
        valid_mask = feats.notna().all(axis=1)
        feats_clean = feats[valid_mask].values
        residuos_clean = residuos[valid_mask.values]
        n_samples = len(feats_clean)

        # Ajustar test_size si es mayor que lo disponible
        effective_test = min(self._test_size, n_samples // (self._n_splits + 1))
        if effective_test < 4:
            logger.warning("Serie muy corta para CV temporal, usando HP por defecto")
            return {}, float("inf")

        tscv = TimeSeriesSplit(n_splits=self._n_splits, test_size=effective_test)

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

            for train_idx, val_idx in tscv.split(feats_clean):
                x_tr, x_val = feats_clean[train_idx], feats_clean[val_idx]
                y_tr, y_val = residuos_clean[train_idx], residuos_clean[val_idx]

                model = XGBRegressor(
                    **hp,
                    n_estimators=self._n_estimators_max,
                    colsample_bytree=0.8,
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
