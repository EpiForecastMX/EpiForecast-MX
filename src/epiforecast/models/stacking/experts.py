"""Expertos para Stacking: Prophet, ETS (Holt-Winters), LightGBM."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.utils.config import logger

logging.getLogger("cmdstanpy").disabled = True


class ProphetExpert:
    """Prophet base con yearly_custom seasonality."""

    def __init__(self, config: dict[str, Any], holidays: pd.DataFrame | None = None):
        self._config = config
        self._holidays = holidays
        self._model: Any = None

    def fit(self, train_data: pd.DataFrame) -> None:
        from prophet import Prophet

        np.random.seed(RANDOM_SEED)
        self._model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=(
                self._holidays if self._holidays is not None and not self._holidays.empty else None
            ),
            changepoint_prior_scale=self._config.get("changepoint_prior_scale", 0.05),
            seasonality_prior_scale=self._config.get("seasonality_prior_scale", 0.1),
            seasonality_mode=self._config.get("seasonality_mode", "additive"),
        )
        yc = self._config.get("yearly_custom", {})
        self._model.add_seasonality(
            name="yearly_custom",
            period=yc.get("period", 365.25),
            fourier_order=yc.get("fourier_order", 10),
        )
        self._model.fit(train_data[["ds", "y"]])
        logger.debug("  ProphetExpert entrenado ({} filas)", len(train_data))

    def predict(self, dates: pd.DataFrame) -> npt.NDArray[np.floating[Any]]:
        if self._model is None:
            raise RuntimeError("ProphetExpert no entrenado.")
        future = dates[["ds"]] if "ds" in dates.columns else dates
        pred = self._model.predict(future)
        yhat: npt.NDArray[np.floating[Any]] = np.clip(pred["yhat"].to_numpy(dtype=float), 0, None)
        return yhat


class ETSExpert:
    """Holt-Winters/ETS con manejo robusto de ceros y series cortas."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._model: Any = None
        self._failed: bool = False
        self._last_value: float = 0.0

    def fit(self, train_data: pd.DataFrame) -> None:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        y = train_data["y"].values.astype(float)
        sp = int(self._config.get("seasonal_periods", 52))
        trend = self._config.get("trend", "add")
        seasonal = self._config.get("seasonal", "add")

        self._last_value = float(y[-1]) if len(y) > 0 else 0.0

        if len(y) < 2 * sp:
            self._failed = True
            logger.debug("  ETSExpert: serie corta ({} < {}), fallback", len(y), 2 * sp)
            return

        try:
            self._model = ExponentialSmoothing(
                y,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=sp,
                initialization_method="estimated",
            ).fit(optimized=True)
            self._failed = False
            logger.debug("  ETSExpert entrenado ({} filas)", len(train_data))
        except (ValueError, np.linalg.LinAlgError) as e:
            logger.warning("  ETSExpert: no convergio ({}), fallback", e)
            self._failed = True

    def predict(self, dates: pd.DataFrame) -> npt.NDArray[np.floating[Any]]:
        n = len(dates)
        if self._failed or self._model is None:
            return np.zeros(n)
        try:
            pred = self._model.forecast(n)
            return np.clip(np.asarray(pred, dtype=float), 0, None)
        except (ValueError, IndexError) as e:
            logger.debug("  ETSExpert: prediccion fallida ({})", e)
            return np.zeros(n)

    def predict_full(
        self, n_forward: int
    ) -> tuple[npt.NDArray[np.floating[Any]] | None, npt.NDArray[np.floating[Any]]]:
        """Retorna (fitted_values, forecast) para in-sample + forward."""
        if self._failed or self._model is None:
            return None, np.zeros(max(n_forward, 0))
        fitted = np.clip(np.asarray(self._model.fittedvalues, dtype=float), 0, None)
        if n_forward > 0:
            fwd = np.clip(np.asarray(self._model.forecast(n_forward), dtype=float), 0, None)
        else:
            fwd = np.array([], dtype=float)
        return fitted, fwd


class LGBMExpert:
    """LightGBM con features trigonometricos deterministas."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._model: Any = None
        self._train_len: int = 0

    def _build_features(self, dates: pd.Series, offset: int = 0) -> pd.DataFrame:
        dates = pd.to_datetime(dates)
        week = np.asarray(dates.dt.isocalendar().week, dtype=float)
        idx = np.arange(len(dates), dtype=float) + offset
        return pd.DataFrame(
            {
                "sin_sem": np.sin(2 * np.pi * week / 52),
                "cos_sem": np.cos(2 * np.pi * week / 52),
                "trend": idx,
            }
        )

    def fit(self, train_data: pd.DataFrame) -> None:
        import lightgbm as lgb

        feats = self._build_features(train_data["ds"])
        y = train_data["y"].values.astype(float)
        self._train_len = len(train_data)

        self._model = lgb.LGBMRegressor(
            n_estimators=int(self._config.get("n_estimators", 300)),
            max_depth=int(self._config.get("max_depth", 4)),
            learning_rate=float(self._config.get("learning_rate", 0.05)),
            subsample=float(self._config.get("subsample", 0.8)),
            num_leaves=int(self._config.get("num_leaves", 31)),
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        self._model.fit(feats, y)
        logger.debug("  LGBMExpert entrenado ({} filas)", len(train_data))

    def predict(
        self, dates: pd.DataFrame, *, trend_start: int | None = None
    ) -> npt.NDArray[np.floating[Any]]:
        if self._model is None:
            raise RuntimeError("LGBMExpert no entrenado.")
        ds = dates["ds"] if "ds" in dates.columns else dates.iloc[:, 0]
        offset = trend_start if trend_start is not None else self._train_len
        feats = self._build_features(ds, offset=offset)
        return np.asarray(np.clip(self._model.predict(feats), 0, None), dtype=float)
