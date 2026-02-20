# src/modelado/comparacion_modelos.py
"""
Módulo de comparación de modelos para forecasting epidemiológico.

Evalúa Prophet, XGBoost, SARIMAX, Ridge, TFT, DeepAR y LightGBM+LSTM
con cross-validation temporal y tracking de experimentos compatible con
SageMaker Experiments.
"""

import gc
import itertools
import json
import logging
import os
import time
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from src.configuraciones.config_params import logger


# ─── Features temporales para modelos tabulares ───────────────────────────────


def crear_features_temporales(df, lags=None, rolling_windows=None):
    """Genera features de calendario y lag para modelos tabulares (XGBoost, Ridge)."""
    if lags is None:
        lags = [1, 2, 4, 12, 52]
    if rolling_windows is None:
        rolling_windows = [4, 12, 26]

    out = df[["ds", "y"]].copy()
    out = out.sort_values("ds").reset_index(drop=True)

    # Calendario
    out["week_of_year"] = out["ds"].dt.isocalendar().week.astype(int)
    out["month"] = out["ds"].dt.month
    out["quarter"] = out["ds"].dt.quarter
    out["year"] = out["ds"].dt.year

    # Encoding cíclico (evita discontinuidad semana 52→1)
    out["week_sin"] = np.sin(2 * np.pi * out["week_of_year"] / 52)
    out["week_cos"] = np.cos(2 * np.pi * out["week_of_year"] / 52)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12)

    # Lags
    for lag in lags:
        out[f"lag_{lag}"] = out["y"].shift(lag)

    # Rolling stats (shift 1 para evitar data leakage)
    for w in rolling_windows:
        out[f"rolling_mean_{w}"] = out["y"].shift(1).rolling(window=w).mean()
        out[f"rolling_std_{w}"] = out["y"].shift(1).rolling(window=w).std()

    return out


def _feature_cols(df):
    """Retorna columnas de features (todo excepto ds, y)."""
    return [c for c in df.columns if c not in ("ds", "y")]


# ─── Clase base de modelo ─────────────────────────────────────────────────────


class ModeloBase(ABC):
    """Interfaz base para todos los modelos de forecasting."""

    nombre: str = "base"

    @abstractmethod
    def fit(self, train_df: pd.DataFrame) -> None:
        """Entrena con DataFrame que contiene columnas ds, y."""

    @abstractmethod
    def predict(self, dates_df: pd.DataFrame) -> np.ndarray:
        """Predice para un DataFrame con columna ds. Retorna array de predicciones."""

    def set_params(self, params: dict) -> None:
        """Configura hiperparámetros. Override en subclases."""
        self._params = params

    def cross_validate(self, train_df, param_grid, n_splits=4, test_size=53,
                       pesos_folds=None):
        """
        CV temporal con grid search y ponderación opcional de folds.

        Args:
            pesos_folds: lista de pesos por fold (ej. [0.5, 0.75, 1.0, 1.25]).
                         Fold 1 (COVID) pesa menos, folds recientes pesan más.
                         None = promedio simple (sin ponderación).

        Returns:
            (mejores_params, mejor_rmse, historial)
        """
        if not param_grid:
            param_list = [{}]
        else:
            keys = list(param_grid.keys())
            combos = list(itertools.product(*param_grid.values()))
            param_list = [dict(zip(keys, v)) for v in combos]

        tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
        best_rmse = float("inf")
        best_params = {}
        historial = []

        logger.info(
            f"[{self.nombre}] {len(param_list)} combinaciones × {n_splits} folds "
            f"= {len(param_list) * n_splits} evaluaciones"
            + (f" (ponderado: {pesos_folds})" if pesos_folds else "")
        )

        for i, params in enumerate(param_list):
            fold_rmses = []

            for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_df)):
                fold_train = train_df.iloc[train_idx]
                fold_val = train_df.iloc[val_idx]

                try:
                    self.set_params(params)
                    self.fit(fold_train)
                    preds = self.predict(fold_val)
                    rmse = np.sqrt(mean_squared_error(fold_val["y"].values, preds))
                    fold_rmses.append(rmse)
                    logger.debug(
                        f"[{self.nombre}] Iter {i + 1} Fold {fold_idx + 1}: RMSE={rmse:.4f}"
                    )
                except Exception as e:
                    logger.warning(f"[{self.nombre}] Error en iter {i + 1} fold {fold_idx + 1}: {e}")
                    continue

            if fold_rmses:
                # Promedio ponderado si hay pesos, simple si no
                if pesos_folds and len(fold_rmses) == len(pesos_folds):
                    weights = np.array(pesos_folds[:len(fold_rmses)])
                    mean_rmse = float(np.average(fold_rmses, weights=weights))
                else:
                    mean_rmse = float(np.mean(fold_rmses))

                std_rmse = float(np.std(fold_rmses))
                historial.append({
                    "params": params,
                    "mean_rmse": mean_rmse,
                    "std_rmse": std_rmse,
                    "fold_rmses": fold_rmses,
                    "folds_completados": len(fold_rmses),
                })
                if mean_rmse < best_rmse:
                    best_rmse = mean_rmse
                    best_params = params
                    logger.info(
                        f"[{self.nombre}] CV iter {i + 1}/{len(param_list)} — "
                        f"Nuevo mejor RMSE: {best_rmse:.4f} ± {std_rmse:.4f}"
                    )

        logger.success(f"[{self.nombre}] Mejor RMSE: {best_rmse:.4f} | Params: {best_params}")
        return best_params, best_rmse, historial


# ─── Prophet ──────────────────────────────────────────────────────────────────


class ModeloProphet(ModeloBase):
    """
    Prophet con soporte para fourier_order como hiperparámetro de grid search.

    Hallazgos clave del CLAUDE.md:
    - fourier_order=20 es la mejora más impactante para Depresión (Benchmark Equipo 16)
    - additive gana ~67% para Alzheimer con log-transform
    - cp=0.01 domina, pero cp=0.03-0.05 es competitivo para Depresión
    - yearly_seasonality=False + add_seasonality custom es el approach correcto
    """

    nombre = "Prophet"

    def __init__(self, periodos_atipicos=None, base_params=None):
        self._params = {}
        self._model = None
        self._periodos_atipicos = periodos_atipicos
        self._base_params = base_params or {
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
        }

    def set_params(self, params):
        self._params = params.copy()

    def fit(self, train_df):
        from prophet import Prophet

        logging.getLogger("cmdstanpy").disabled = True

        holidays = None
        if self._periodos_atipicos:
            holidays = pd.DataFrame(self._periodos_atipicos)
            holidays["ds"] = pd.to_datetime(holidays["ds"])

        # Separar fourier_order del resto de params (no es parámetro de Prophet())
        prophet_params = {k: v for k, v in self._params.items() if k != "fourier_order"}
        fourier_order = self._params.get("fourier_order", 10)

        model = Prophet(holidays=holidays, **self._base_params, **prophet_params)

        # Estacionalidad anual custom con Fourier configurable
        # period=52.18 = 365.25/7 (anual exacto en semanas)
        model.add_seasonality(
            name="yearly_custom",
            period=52.18,
            fourier_order=fourier_order,
        )

        model.fit(train_df[["ds", "y"]])
        self._model = model

    def predict(self, dates_df):
        forecast = self._model.predict(dates_df[["ds"]])
        return forecast["yhat"].values


# ─── XGBoost ──────────────────────────────────────────────────────────────────


class ModeloXGBoost(ModeloBase):
    nombre = "XGBoost"

    def __init__(self, lags=None, rolling_windows=None):
        self._params = {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.05}
        self._model = None
        self._lags = lags or [1, 2, 4, 8, 12, 52]
        self._rolling_windows = rolling_windows or [4, 12, 26]
        self._train_df_full = None
        self._feat_cols = None

    def set_params(self, params):
        base = {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.05}
        self._params = {**base, **params}

    def fit(self, train_df):
        import xgboost as xgb

        featured = crear_features_temporales(
            train_df, lags=self._lags, rolling_windows=self._rolling_windows
        )
        featured = featured.dropna()
        self._train_df_full = train_df.copy()

        self._feat_cols = _feature_cols(featured)
        X = featured[self._feat_cols].values
        y = featured["y"].values

        self._model = xgb.XGBRegressor(**self._params, random_state=42, verbosity=0)
        self._model.fit(X, y)

    def predict(self, dates_df):
        # Concatenar train + dates para calcular lags correctamente
        combined = pd.concat([
            self._train_df_full[["ds", "y"]],
            dates_df[["ds"]].assign(y=np.nan),
        ]).reset_index(drop=True)

        featured = crear_features_temporales(
            combined, lags=self._lags, rolling_windows=self._rolling_windows
        )

        mask = featured["ds"].isin(dates_df["ds"])
        pred_features = featured.loc[mask, self._feat_cols].ffill().bfill()

        return self._model.predict(pred_features.values)


# ─── SARIMAX ──────────────────────────────────────────────────────────────────


class ModeloSARIMAX(ModeloBase):
    """SARIMAX de statsmodels. NOTA: con seasonal_order s=52 puede ser lento (~2-5 min/fold)."""

    nombre = "SARIMAX"

    def __init__(self):
        self._params = {"order": (1, 1, 1), "seasonal_order": (0, 0, 0, 0)}
        self._model = None
        self._train_series = None

    def set_params(self, params):
        parsed = {}
        for k, v in params.items():
            parsed[k] = tuple(v) if isinstance(v, list) else v
        self._params = parsed

    def fit(self, train_df):
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        warnings.filterwarnings("ignore", category=UserWarning)

        series = train_df.set_index("ds")["y"].asfreq("W-MON")
        series = series.ffill()
        self._train_series = series

        order = self._params.get("order", (1, 1, 1))
        seasonal = self._params.get("seasonal_order", (0, 0, 0, 0))

        model = SARIMAX(
            series,
            order=order,
            seasonal_order=seasonal,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self._model = model.fit(disp=False, maxiter=200)

    def predict(self, dates_df):
        start = dates_df["ds"].min()
        end = dates_df["ds"].max()
        forecast = self._model.predict(start=start, end=end)

        result = dates_df[["ds"]].merge(
            forecast.reset_index().rename(columns={"index": "ds", 0: "yhat"}),
            on="ds",
            how="left",
        )
        return result["yhat"].fillna(0).values

    def cross_validate(self, train_df, param_grid, n_splits=4, test_size=53,
                       pesos_folds=None):
        """CV especial para SARIMAX: order y seasonal_order son tuplas, no escalares."""
        orders = param_grid.get("order", [(1, 1, 1)])
        seasonal_orders = param_grid.get("seasonal_order", [(0, 0, 0, 0)])

        tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
        best_rmse = float("inf")
        best_params = {}
        historial = []
        total_combos = len(orders) * len(seasonal_orders)

        logger.info(
            f"[SARIMAX] {total_combos} combinaciones × {n_splits} folds "
            f"= {total_combos * n_splits} evaluaciones"
        )

        combo_idx = 0
        for order in orders:
            for seasonal in seasonal_orders:
                combo_idx += 1
                params = {
                    "order": tuple(order) if isinstance(order, list) else order,
                    "seasonal_order": tuple(seasonal) if isinstance(seasonal, list) else seasonal,
                }
                fold_rmses = []

                for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(train_df)):
                    fold_train = train_df.iloc[train_idx]
                    fold_val = train_df.iloc[val_idx]

                    try:
                        self.set_params(params)
                        self.fit(fold_train)
                        preds = self.predict(fold_val)
                        rmse = np.sqrt(mean_squared_error(fold_val["y"].values, preds))
                        fold_rmses.append(rmse)
                    except Exception as e:
                        logger.debug(f"[SARIMAX] Fold {fold_idx + 1} error con {params}: {e}")
                        continue

                if fold_rmses:
                    if pesos_folds and len(fold_rmses) == len(pesos_folds):
                        weights = np.array(pesos_folds[:len(fold_rmses)])
                        mean_rmse = float(np.average(fold_rmses, weights=weights))
                    else:
                        mean_rmse = float(np.mean(fold_rmses))
                    std_rmse = float(np.std(fold_rmses))
                    historial.append({
                        "params": params,
                        "mean_rmse": mean_rmse,
                        "std_rmse": std_rmse,
                        "folds_completados": len(fold_rmses),
                    })
                    if mean_rmse < best_rmse:
                        best_rmse = mean_rmse
                        best_params = params
                        logger.info(
                            f"[SARIMAX] Combo {combo_idx}/{total_combos} — "
                            f"Nuevo mejor RMSE: {best_rmse:.4f} ± {std_rmse:.4f}"
                        )

        logger.success(f"[SARIMAX] Mejor RMSE: {best_rmse:.4f} | Params: {best_params}")
        return best_params, best_rmse, historial


# ─── Ridge ────────────────────────────────────────────────────────────────────


class ModeloRidge(ModeloBase):
    nombre = "Ridge"

    def __init__(self, lags=None, rolling_windows=None):
        self._params = {"alpha": 1.0}
        self._model = None
        self._lags = lags or [1, 2, 4, 8, 12, 52]
        self._rolling_windows = rolling_windows or [4, 12, 26]
        self._train_df_full = None
        self._scaler = None
        self._feat_cols = None

    def set_params(self, params):
        self._params = {"alpha": 1.0, **params}

    def fit(self, train_df):
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler

        featured = crear_features_temporales(
            train_df, lags=self._lags, rolling_windows=self._rolling_windows
        )
        featured = featured.dropna()
        self._train_df_full = train_df.copy()

        self._feat_cols = _feature_cols(featured)
        X = featured[self._feat_cols].values
        y = featured["y"].values

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._model = Ridge(alpha=self._params.get("alpha", 1.0))
        self._model.fit(X_scaled, y)

    def predict(self, dates_df):
        combined = pd.concat([
            self._train_df_full[["ds", "y"]],
            dates_df[["ds"]].assign(y=np.nan),
        ]).reset_index(drop=True)

        featured = crear_features_temporales(
            combined, lags=self._lags, rolling_windows=self._rolling_windows
        )
        mask = featured["ds"].isin(dates_df["ds"])
        pred_features = featured.loc[mask, self._feat_cols].ffill().bfill()

        X_scaled = self._scaler.transform(pred_features.values)
        return self._model.predict(X_scaled)


# ─── Temporal Fusion Transformer (TFT) ────────────────────────────────────────


class ModeloTFT(ModeloBase):
    """
    Temporal Fusion Transformer — estado del arte en forecasting interpretable.
    Maneja covariables estáticas, entradas temporales conocidas y desconocidas.
    Requiere: pip install neuralforecast
    """

    nombre = "TFT"

    def __init__(self):
        self._default_params = {
            "hidden_size": 16,
            "n_head": 1,
            "dropout": 0.1,
            "learning_rate": 0.003,
            "max_steps": 200,
            "input_size": 104,
        }
        self._params = dict(self._default_params)
        self._nf = None
        self._h = 52
        self._train_df = None

    def set_params(self, params):
        self._params = {**self._default_params, **params}

    def fit(self, train_df):
        from neuralforecast import NeuralForecast
        from neuralforecast.models import TFT

        os.environ["NIXTLA_ID_AS_COL"] = "true"
        warnings.filterwarnings("ignore", module="pytorch_lightning")
        warnings.filterwarnings("ignore", module="lightning")

        df = train_df[["ds", "y"]].copy()
        df["unique_id"] = "series"
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)
        self._train_df = df

        input_size = min(self._params["input_size"], max(10, len(df) // 3))

        model = TFT(
            h=self._h,
            input_size=input_size,
            hidden_size=self._params["hidden_size"],
            n_head=self._params["n_head"],
            dropout=self._params["dropout"],
            learning_rate=self._params["learning_rate"],
            max_steps=self._params["max_steps"],
            scaler_type="standard",
            random_seed=42,
            trainer_kwargs={"enable_progress_bar": False, "enable_model_summary": False},
        )

        self._nf = NeuralForecast(models=[model], freq="W-MON")
        self._nf.fit(df=df)

    def predict(self, dates_df):
        n_steps = len(dates_df)
        forecasts = self._nf.predict()
        preds = forecasts["TFT"].values

        if len(preds) >= n_steps:
            return preds[:n_steps]
        return np.pad(preds, (0, n_steps - len(preds)), constant_values=preds[-1])

    def cross_validate(self, train_df, param_grid, n_splits=4, test_size=53):
        self._h = test_size
        result = super().cross_validate(train_df, param_grid, n_splits, test_size)
        gc.collect()
        return result


# ─── DeepAR (Probabilistic Forecasting) ──────────────────────────────────────


class ModeloDeepAR(ModeloBase):
    """
    DeepAR — forecasting probabilístico con autoregresión profunda.
    Genera distribuciones de probabilidad (útil para rangos de incertidumbre).
    Recomendado por Dra. Grettel Barceló para series con pocas observaciones.
    Requiere: pip install neuralforecast
    """

    nombre = "DeepAR"

    def __init__(self):
        self._default_params = {
            "hidden_size": 32,
            "n_layers": 2,
            "dropout": 0.1,
            "learning_rate": 0.001,
            "max_steps": 200,
            "input_size": 104,
        }
        self._params = dict(self._default_params)
        self._nf = None
        self._h = 52
        self._train_df = None

    def set_params(self, params):
        self._params = {**self._default_params, **params}

    def fit(self, train_df):
        from neuralforecast import NeuralForecast
        from neuralforecast.models import DeepAR

        os.environ["NIXTLA_ID_AS_COL"] = "true"
        warnings.filterwarnings("ignore", module="pytorch_lightning")
        warnings.filterwarnings("ignore", module="lightning")

        df = train_df[["ds", "y"]].copy()
        df["unique_id"] = "series"
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)
        self._train_df = df

        input_size = min(self._params["input_size"], max(10, len(df) // 3))

        model = DeepAR(
            h=self._h,
            input_size=input_size,
            hidden_size=self._params["hidden_size"],
            n_layers=self._params.get("n_layers", 2),
            dropout=self._params["dropout"],
            learning_rate=self._params["learning_rate"],
            max_steps=self._params["max_steps"],
            scaler_type="standard",
            random_seed=42,
            trainer_kwargs={"enable_progress_bar": False, "enable_model_summary": False},
        )

        self._nf = NeuralForecast(models=[model], freq="W-MON")
        self._nf.fit(df=df)

    def predict(self, dates_df):
        n_steps = len(dates_df)
        forecasts = self._nf.predict()

        # DeepAR puede devolver columna "DeepAR" o "DeepAR-median"
        if "DeepAR" in forecasts.columns:
            preds = forecasts["DeepAR"].values
        elif "DeepAR-median" in forecasts.columns:
            preds = forecasts["DeepAR-median"].values
        else:
            cols = [c for c in forecasts.columns if c.startswith("DeepAR")]
            preds = forecasts[cols[0]].values

        if len(preds) >= n_steps:
            return preds[:n_steps]
        return np.pad(preds, (0, n_steps - len(preds)), constant_values=preds[-1])

    def cross_validate(self, train_df, param_grid, n_splits=4, test_size=53):
        self._h = test_size
        result = super().cross_validate(train_df, param_grid, n_splits, test_size)
        gc.collect()
        return result


# ─── LightGBM + LSTM Híbrido ─────────────────────────────────────────────────


class ModeloLightGBM_LSTM(ModeloBase):
    """
    Modelo híbrido: LightGBM (features tabulares) + LSTM (patrones secuenciales).
    Ensemble por promedio ponderado configurable.
    Requiere: pip install lightgbm neuralforecast
    """

    nombre = "LightGBM+LSTM"

    def __init__(self, lags=None, rolling_windows=None):
        self._default_params = {
            "lgbm_n_estimators": 300,
            "lgbm_max_depth": 5,
            "lgbm_learning_rate": 0.05,
            "lstm_hidden_size": 32,
            "lstm_n_layers": 2,
            "lstm_max_steps": 200,
            "ensemble_weight_lgbm": 0.5,
        }
        self._params = dict(self._default_params)
        self._lgbm = None
        self._nf_lstm = None
        self._lags = lags or [1, 2, 4, 8, 12, 52]
        self._rolling_windows = rolling_windows or [4, 12, 26]
        self._train_df_full = None
        self._feat_cols = None
        self._h = 52

    def set_params(self, params):
        self._params = {**self._default_params, **params}

    def fit(self, train_df):
        import lightgbm as lgb
        from neuralforecast import NeuralForecast
        from neuralforecast.models import LSTM

        os.environ["NIXTLA_ID_AS_COL"] = "true"
        warnings.filterwarnings("ignore", module="pytorch_lightning")
        warnings.filterwarnings("ignore", module="lightning")

        self._train_df_full = train_df.copy()

        # ── LightGBM (features tabulares) ──
        featured = crear_features_temporales(
            train_df, lags=self._lags, rolling_windows=self._rolling_windows
        )
        featured = featured.dropna()

        self._feat_cols = _feature_cols(featured)
        X = featured[self._feat_cols].values
        y = featured["y"].values

        self._lgbm = lgb.LGBMRegressor(
            n_estimators=self._params["lgbm_n_estimators"],
            max_depth=self._params["lgbm_max_depth"],
            learning_rate=self._params["lgbm_learning_rate"],
            random_state=42,
            verbosity=-1,
        )
        self._lgbm.fit(X, y)

        # ── LSTM (patrones secuenciales) ──
        df_lstm = train_df[["ds", "y"]].copy()
        df_lstm["unique_id"] = "series"
        df_lstm["ds"] = pd.to_datetime(df_lstm["ds"])
        df_lstm = df_lstm.sort_values("ds").reset_index(drop=True)

        input_size = min(104, max(10, len(df_lstm) // 3))

        model = LSTM(
            h=self._h,
            input_size=input_size,
            hidden_size=self._params["lstm_hidden_size"],
            n_layers=self._params.get("lstm_n_layers", 2),
            max_steps=self._params["lstm_max_steps"],
            scaler_type="standard",
            random_seed=42,
            trainer_kwargs={"enable_progress_bar": False, "enable_model_summary": False},
        )

        self._nf_lstm = NeuralForecast(models=[model], freq="W-MON")
        self._nf_lstm.fit(df=df_lstm)

    def predict(self, dates_df):
        n_steps = len(dates_df)
        weight = self._params.get("ensemble_weight_lgbm", 0.5)

        # ── LightGBM ──
        combined = pd.concat([
            self._train_df_full[["ds", "y"]],
            dates_df[["ds"]].assign(y=np.nan),
        ]).reset_index(drop=True)

        featured = crear_features_temporales(
            combined, lags=self._lags, rolling_windows=self._rolling_windows
        )
        mask = featured["ds"].isin(dates_df["ds"])
        pred_features = featured.loc[mask, self._feat_cols].ffill().bfill()
        lgbm_preds = self._lgbm.predict(pred_features.values)

        # ── LSTM ──
        lstm_forecasts = self._nf_lstm.predict()
        lstm_preds = lstm_forecasts["LSTM"].values

        if len(lstm_preds) < n_steps:
            lstm_preds = np.pad(
                lstm_preds,
                (0, n_steps - len(lstm_preds)),
                constant_values=lstm_preds[-1] if len(lstm_preds) > 0 else 0,
            )
        else:
            lstm_preds = lstm_preds[:n_steps]

        # ── Ensemble ponderado ──
        return weight * lgbm_preds + (1 - weight) * lstm_preds

    def cross_validate(self, train_df, param_grid, n_splits=4, test_size=53):
        self._h = test_size
        result = super().cross_validate(train_df, param_grid, n_splits, test_size)
        gc.collect()
        return result


# ─── Experiment Tracker ───────────────────────────────────────────────────────


class ExperimentTracker:
    """
    Registra métricas, parámetros y artefactos de experimentos.
    Compatible con ejecución local (CSV/JSON) y SageMaker Experiments.
    """

    def __init__(self, nombre_experimento, directorio="./experiments", usar_sagemaker=False):
        self.nombre = nombre_experimento
        self.directorio = Path(directorio)
        self.directorio.mkdir(parents=True, exist_ok=True)
        self.usar_sagemaker = usar_sagemaker
        self._resultados = []
        self._trial_actual = None
        self._run_sagemaker = None
        self._timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info(f"Experimento '{nombre_experimento}' iniciado | {self._timestamp}")

    def iniciar_trial(self, nombre_trial):
        """Inicia un trial (una combinación modelo/datos específica)."""
        self._trial_actual = {
            "trial": nombre_trial,
            "timestamp": datetime.now().isoformat(),
            "parametros": {},
            "metricas": {},
        }
        logger.info(f"─── Trial: {nombre_trial} ───")

        if self.usar_sagemaker:
            try:
                from sagemaker.experiments.run import Run

                self._run_sagemaker = Run(
                    experiment_name=self.nombre,
                    run_name=nombre_trial,
                )
                self._run_sagemaker.__enter__()
            except ImportError:
                logger.warning("sagemaker SDK no disponible, usando solo tracking local")
                self.usar_sagemaker = False

    def log_parametro(self, nombre, valor):
        """Registra un hiperparámetro."""
        self._trial_actual["parametros"][nombre] = valor
        if self.usar_sagemaker and self._run_sagemaker:
            self._run_sagemaker.log_parameter(nombre, str(valor))

    def log_parametros(self, params: dict):
        """Registra múltiples hiperparámetros."""
        for k, v in params.items():
            self.log_parametro(k, v)

    def log_metrica(self, nombre, valor, paso=None):
        """Registra una métrica."""
        self._trial_actual["metricas"][nombre] = valor
        logger.info(f"  {nombre}: {valor:.4f}")
        if self.usar_sagemaker and self._run_sagemaker:
            self._run_sagemaker.log_metric(nombre, valor, step=paso)

    def finalizar_trial(self):
        """Cierra el trial actual y guarda resultados."""
        self._resultados.append(self._trial_actual)

        if self.usar_sagemaker and self._run_sagemaker:
            try:
                self._run_sagemaker.__exit__(None, None, None)
            except Exception:
                pass
            self._run_sagemaker = None

    def guardar_resumen(self):
        """Guarda resumen completo en CSV y JSON."""
        # JSON con detalle completo
        ruta_json = self.directorio / f"{self.nombre}_{self._timestamp}.json"
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(self._resultados, f, indent=2, ensure_ascii=False, default=str)
        logger.success(f"Resultados JSON guardados: {ruta_json}")

        # CSV resumen plano
        filas = []
        for r in self._resultados:
            fila = {"trial": r["trial"], "timestamp": r["timestamp"]}
            fila.update({f"param_{k}": v for k, v in r["parametros"].items()})
            fila.update(r["metricas"])
            filas.append(fila)

        if filas:
            df = pd.DataFrame(filas)
            ruta_csv = self.directorio / f"{self.nombre}_{self._timestamp}.csv"
            df.to_csv(ruta_csv, index=False, encoding="utf-8")
            logger.success(f"Resumen CSV guardado: {ruta_csv}")

            # Imprimir ranking por RMSE
            if "cv_rmse" in df.columns:
                ranking = df.dropna(subset=["cv_rmse"]).sort_values("cv_rmse")
                logger.info("═══ Ranking de modelos (CV RMSE) ═══")
                for pos, (_, row) in enumerate(ranking.iterrows(), 1):
                    test_info = ""
                    if "test_rmse" in row and pd.notna(row.get("test_rmse")):
                        test_info = f" | Test RMSE: {row['test_rmse']:.4f}"
                    logger.info(
                        f"  #{pos} {row['trial']}: CV RMSE={row['cv_rmse']:.4f}{test_info}"
                    )

        return self._resultados


# ─── Comparador de Modelos ────────────────────────────────────────────────────


class ComparadorModelos:
    """
    Orquesta la comparación de múltiples modelos sobre los mismos datos
    con cross-validation temporal y tracking de experimentos.

    Mejoras incorporadas del CLAUDE.md:
    - Grids diferenciados por padecimiento para Prophet
    - Ponderación de folds (COVID Fold 1 pesa menos)
    - Log-transform del target
    - Filtrado de series vacías (>95% zeros)

    Uso:
        config = OmegaConf.load("config/experimentos.yaml")
        comparador = ComparadorModelos(config["experimentos"])
        comparador.ejecutar(df_serie, "Depresión", "incrementos_total")
        comparador.guardar_resultados()
    """

    def __init__(self, config_experimentos: dict):
        self.config = config_experimentos

        cv_conf = config_experimentos.get("cv", {})
        self.n_splits = cv_conf.get("n_splits", 4)
        self.test_size = cv_conf.get("test_size", 52)
        self.fecha_corte = cv_conf.get("fecha_corte", "2025-01-01")

        # Ponderación de folds (COVID correction)
        self.ponderar_folds = cv_conf.get("ponderar_folds", False)
        self.pesos_folds = cv_conf.get("pesos_folds", None)

        # Log-transform config
        transf = config_experimentos.get("transformacion", {})
        self.log_transform = transf.get("log_transform", True)

        tracking_conf = config_experimentos.get("tracking", {})
        self.tracker = ExperimentTracker(
            nombre_experimento=config_experimentos.get("nombre", "epiforecast-exp"),
            directorio=tracking_conf.get("directorio_resultados", "./experiments"),
            usar_sagemaker=tracking_conf.get("sagemaker", False),
        )

    def _obtener_grid_prophet(self, padecimiento=None):
        """
        Obtiene el grid de Prophet específico para el padecimiento.
        Si no hay grid específico, usa el grid base.
        """
        config_prophet = self.config.get("modelos", {}).get("prophet", {})
        grids_especificos = config_prophet.get("grids_por_padecimiento", {})

        if padecimiento and padecimiento in grids_especificos:
            grid = grids_especificos[padecimiento]
            logger.info(f"[Prophet] Usando grid específico para {padecimiento}")
        else:
            grid = config_prophet.get("param_grid", {})
            logger.info(f"[Prophet] Usando grid base (sin específico para {padecimiento})")

        return grid

    def _crear_modelos(self, periodos_atipicos=None, padecimiento=None):
        """Instancia los modelos activos según configuración."""
        config_modelos = self.config.get("modelos", {})
        modelos = []

        if config_modelos.get("prophet", {}).get("activo", False):
            grid = self._obtener_grid_prophet(padecimiento)
            modelos.append((
                ModeloProphet(periodos_atipicos=periodos_atipicos),
                grid,
            ))

        if config_modelos.get("xgboost", {}).get("activo", False):
            feat_conf = config_modelos["xgboost"].get("features", {})
            modelos.append((
                ModeloXGBoost(
                    lags=feat_conf.get("lags"),
                    rolling_windows=feat_conf.get("rolling_windows"),
                ),
                config_modelos["xgboost"].get("param_grid", {}),
            ))

        if config_modelos.get("sarimax", {}).get("activo", False):
            modelos.append((
                ModeloSARIMAX(),
                config_modelos["sarimax"].get("param_grid", {}),
            ))

        if config_modelos.get("ridge", {}).get("activo", False):
            feat_conf = config_modelos["ridge"].get("features", {})
            modelos.append((
                ModeloRidge(
                    lags=feat_conf.get("lags"),
                    rolling_windows=feat_conf.get("rolling_windows"),
                ),
                config_modelos["ridge"].get("param_grid", {}),
            ))

        # ── Modelos Deep Learning (requieren neuralforecast) ──
        if config_modelos.get("tft", {}).get("activo", False):
            try:
                import neuralforecast  # noqa: F401

                modelos.append((
                    ModeloTFT(),
                    config_modelos["tft"].get("param_grid", {}),
                ))
            except ImportError:
                logger.warning(
                    "neuralforecast no instalado — TFT desactivado. "
                    "Instalar: pip install -r aws/requirements_dl.txt"
                )

        if config_modelos.get("deepar", {}).get("activo", False):
            try:
                import neuralforecast  # noqa: F401

                modelos.append((
                    ModeloDeepAR(),
                    config_modelos["deepar"].get("param_grid", {}),
                ))
            except ImportError:
                logger.warning(
                    "neuralforecast no instalado — DeepAR desactivado. "
                    "Instalar: pip install -r aws/requirements_dl.txt"
                )

        if config_modelos.get("lightgbm_lstm", {}).get("activo", False):
            try:
                import lightgbm  # noqa: F401
                import neuralforecast  # noqa: F401

                feat_conf = config_modelos["lightgbm_lstm"].get("features", {})
                modelos.append((
                    ModeloLightGBM_LSTM(
                        lags=feat_conf.get("lags"),
                        rolling_windows=feat_conf.get("rolling_windows"),
                    ),
                    config_modelos["lightgbm_lstm"].get("param_grid", {}),
                ))
            except ImportError:
                logger.warning(
                    "lightgbm y/o neuralforecast no instalados — LightGBM+LSTM desactivado. "
                    "Instalar: pip install -r aws/requirements_dl.txt"
                )

        return modelos

    def _serie_es_viable(self, df, umbral_zeros=0.95):
        """
        Filtra series con >95% zeros (ej. BCS Alzheimer).
        RMSE=0 en estas series es engañoso, no deberían entrenarse.
        """
        proporcion_zeros = (df["y"] == 0).sum() / len(df)
        if proporcion_zeros > umbral_zeros:
            return False, proporcion_zeros
        return True, proporcion_zeros

    def ejecutar(self, df, padecimiento, sexo, region=None, periodos_atipicos=None):
        """
        Ejecuta comparación de todos los modelos activos.

        Args:
            df: DataFrame con columnas ds, y (serie temporal ya agrupada)
            padecimiento: nombre del padecimiento (para grid diferenciado)
            sexo: etiqueta de sexo
            region: entidad/región (None = nacional)
            periodos_atipicos: lista de dicts para Prophet holidays

        Returns:
            Lista de dicts con resultados por modelo
        """
        nivel = region or "Nacional"
        logger.info(f"══════ Comparando modelos | {padecimiento} | {nivel} | {sexo} ══════")

        # ── Filtrar series vacías ──
        es_viable, pct_zeros = self._serie_es_viable(df)
        if not es_viable:
            logger.warning(
                f"⚠️ Serie {padecimiento}/{nivel}/{sexo} tiene {pct_zeros:.0%} zeros — "
                f"OMITIDA (umbral >95%). RMSE=0 sería engañoso."
            )
            return []

        # ── Log-transform ──
        if self.log_transform:
            df = df.copy()
            df["y_original"] = df["y"].copy()
            df["y"] = np.log1p(df["y"])  # log(1 + y)
            logger.info(f"Log-transform aplicado: rango y [{df['y'].min():.3f}, {df['y'].max():.3f}]")

        # Split train/test
        df["ds"] = pd.to_datetime(df["ds"])
        train_df = df[df["ds"] < self.fecha_corte].copy()
        test_df = df[df["ds"] >= self.fecha_corte].copy()
        logger.info(
            f"Train: {len(train_df)} semanas (hasta {train_df['ds'].max().date()}) | "
            f"Test: {len(test_df)} semanas"
        )

        modelos = self._crear_modelos(periodos_atipicos, padecimiento=padecimiento)
        resultados = []

        # Pesos de folds para CV
        pesos = self.pesos_folds if self.ponderar_folds else None

        for modelo, param_grid in modelos:
            trial_name = f"{modelo.nombre}_{padecimiento}_{nivel}_{sexo}"
            self.tracker.iniciar_trial(trial_name)

            self.tracker.log_parametros({
                "modelo": modelo.nombre,
                "padecimiento": padecimiento,
                "sexo": sexo,
                "nivel": nivel,
                "train_size": len(train_df),
                "test_size": len(test_df),
                "log_transform": self.log_transform,
                "ponderar_folds": self.ponderar_folds,
            })

            inicio = time.time()

            try:
                # Cross-validation con grid search (ponderado si configurado)
                best_params, best_rmse, historial = modelo.cross_validate(
                    train_df, param_grid, self.n_splits, self.test_size,
                    pesos_folds=pesos,
                )

                # Entrenar modelo final con mejores parámetros
                modelo.set_params(best_params)
                modelo.fit(train_df)

                self.tracker.log_metrica("cv_rmse", best_rmse)

                # Evaluar en test set si hay datos
                if len(test_df) > 0:
                    preds = modelo.predict(test_df)
                    y_true = test_df["y"].values

                    test_rmse = np.sqrt(mean_squared_error(y_true, preds))
                    test_mae = mean_absolute_error(y_true, preds)

                    mask_nonzero = y_true != 0
                    if mask_nonzero.any():
                        test_mape = (
                            mean_absolute_percentage_error(
                                y_true[mask_nonzero], preds[mask_nonzero]
                            )
                            * 100
                        )
                    else:
                        test_mape = float("nan")

                    self.tracker.log_metrica("test_rmse", test_rmse)
                    self.tracker.log_metrica("test_mae", test_mae)
                    self.tracker.log_metrica("test_mape", test_mape)

                    # Si log-transform, también reportar métricas en escala original
                    if self.log_transform and "y_original" in test_df.columns:
                        y_orig = test_df["y_original"].values
                        preds_orig = np.expm1(preds)  # exp(x) - 1
                        preds_orig = np.maximum(preds_orig, 0)  # no negativos
                        test_rmse_orig = np.sqrt(mean_squared_error(y_orig, preds_orig))
                        self.tracker.log_metrica("test_rmse_original_scale", test_rmse_orig)

                # Guardar mejores hiperparámetros
                self.tracker.log_parametros(
                    {f"best_{k}": v for k, v in best_params.items()}
                )

            except Exception as e:
                logger.error(f"[{modelo.nombre}] Error fatal: {e}")
                self.tracker.log_metrica("cv_rmse", float("nan"))
                self.tracker.log_parametro("error", str(e))

            duracion = time.time() - inicio
            self.tracker.log_metrica("duracion_segundos", duracion)
            self.tracker.finalizar_trial()

            resultados.append({
                "modelo": modelo.nombre,
                "padecimiento": padecimiento,
                "sexo": sexo,
                "nivel": nivel,
                "best_params": best_params,
            })

        return resultados

    def guardar_resultados(self):
        """Persiste todos los resultados del experimento."""
        return self.tracker.guardar_resumen()
