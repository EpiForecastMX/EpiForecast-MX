"""XGBDirect: XGBoost que predice y directamente (no residuos).

Usado en modo paralelo del Ensemble: Prophet y XGBDirect predicen
independientemente, luego se combinan con pesos Ridge OOF.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.models.ensemble.feature_builder import construir_features_xgb


class XGBDirectForecaster:
    """XGBoost que predice y directamente (sin residuos Prophet)."""

    def __init__(self, xgb_hp: dict[str, Any]) -> None:
        self._xgb_hp = xgb_hp
        self._model: Any = None

    def fit(self, train_data: pd.DataFrame) -> None:
        """Entrena XGBRegressor sobre y (no residuos)."""
        from xgboost import XGBRegressor

        y_reset = train_data["y"].reset_index(drop=True)
        ds_reset = train_data["ds"].reset_index(drop=True)
        feats = construir_features_xgb(y_reset, ds_reset)

        valid_mask = feats.notna().all(axis=1)
        feats_valid = feats[valid_mask]
        y_valid = y_reset[valid_mask].to_numpy(dtype=float)

        # Early stopping: ultimo 20%
        n_val = max(int(len(feats_valid) * 0.2), 1)
        n_train = len(feats_valid) - n_val

        self._model = XGBRegressor(**self._xgb_hp, n_jobs=-1, random_state=RANDOM_SEED)
        self._model.fit(
            feats_valid.iloc[:n_train],
            y_valid[:n_train],
            eval_set=[(feats_valid.iloc[n_train:], y_valid[n_train:])],
            verbose=False,
        )

    def predict_insample(self, data: pd.DataFrame) -> npt.NDArray[np.floating[Any]]:
        """Prediccion batch sobre datos con y conocido."""
        if self._model is None:
            raise RuntimeError("XGBDirect no entrenado.")

        y_reset = data["y"].reset_index(drop=True)
        ds_reset = data["ds"].reset_index(drop=True)
        feats = construir_features_xgb(y_reset, ds_reset)

        valid_mask = feats.notna().all(axis=1)
        result = np.zeros(len(data))
        if valid_mask.any():
            result[valid_mask.values] = self._model.predict(feats[valid_mask])
        return result

    def predict_recursive(
        self,
        train_data: pd.DataFrame,
        future_dates: npt.NDArray[Any] | pd.DatetimeIndex,
    ) -> npt.NDArray[np.floating[Any]]:
        """Prediccion recursiva extendiendo y_ext con predicciones."""
        if self._model is None:
            raise RuntimeError("XGBDirect no entrenado.")

        y_ext = train_data["y"].values.tolist()
        d_ext = train_data["ds"].values.tolist()
        preds: list[float] = []

        for i in range(len(future_dates)):
            feats = construir_features_xgb(pd.Series(y_ext), pd.Series(pd.to_datetime(d_ext)))
            pred = float(self._model.predict(feats.iloc[[-1]].fillna(0))[0])
            preds.append(pred)
            y_ext.append(pred)
            d_ext.append(future_dates[i])

        return np.array(preds)
