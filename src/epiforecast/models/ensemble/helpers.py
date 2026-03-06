# src/epiforecast/models/ensemble/helpers.py
"""Ensemble helper functions: data preparation, predictions, metrics.

Extracted from model.py for SRP compliance (max 300 lines per module).
Feature engineering moved to feature_builder.py.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.models.ensemble.feature_builder import (  # noqa: F401 – re-export
    FEATURE_NAMES,
    construir_features_xgb,
    construir_holidays,
)
from epiforecast.utils.config import logger

__all__ = [
    "FEATURE_NAMES",
    "construir_features_xgb",
    "construir_holidays",
    "preparar_datos_ensemble",
    "_predecir_test_recursivo",
    "generar_predicciones_insample",
    "generar_prediccion_completa",
    "calcular_metricas_ensemble",
    "calcular_metricas_prophet_base",
]


def preparar_datos_ensemble(
    df: pd.DataFrame,
    padecimiento: str | None,
    sexo: str,
    cutoff: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carga y prepara datos desde el DataFrame proporcionado.

    Returns:
        (serie, train_data, test_data) — DataFrames con columnas ds, y.
    """
    if df.empty:
        raise ValueError("DataFrame vacio. Proporcionar df en __init__.")

    work = df.copy()
    if "Fecha" in work.columns:
        work["Fecha"] = pd.to_datetime(work["Fecha"])

    # Resolver nombre del padecimiento en el CSV
    padecimiento_tipo = padecimiento or "General"
    if "Padecimiento" in work.columns:
        padecimientos_csv = work["Padecimiento"].unique()
        nombre_csv = padecimiento_tipo
        for p in padecimientos_csv:
            if (
                p.lower().replace("\u00e9", "e").replace("\u00f3", "o")
                == padecimiento_tipo.lower()
            ):
                nombre_csv = p
                break
        df_filtrado = work[work["Padecimiento"] == nombre_csv].copy()
    else:
        df_filtrado = work

    col_fecha = "Fecha" if "Fecha" in df_filtrado.columns else "ds"

    # Agregar a nivel nacional si hay columna de sexo
    col_poblacion = "Total"
    if sexo in df_filtrado.columns:
        agg_cols = [sexo]
        if col_poblacion in df_filtrado.columns:
            agg_cols.append(col_poblacion)
        serie = (
            df_filtrado.groupby(col_fecha, as_index=False)[agg_cols]
            .sum()
            .rename(columns={col_fecha: "ds", sexo: "y"})
            .sort_values("ds")
            .reset_index(drop=True)
        )
        serie["y_original"] = serie["y"]
    elif "y" in df_filtrado.columns and "ds" in df_filtrado.columns:
        cols = ["ds", "y"]
        if col_poblacion in df_filtrado.columns:
            cols.append(col_poblacion)
        serie = df_filtrado[cols].copy().sort_values("ds").reset_index(drop=True)
        if "y_original" not in serie.columns:
            serie["y_original"] = serie["y"]
    else:
        raise ValueError(
            f"No se encontro columna '{sexo}' ni 'y' en el DataFrame. "
            f"Columnas: {list(df_filtrado.columns)}"
        )

    # Reordenar columnas para consistencia con Prophet: ds, Total, y_original, y
    col_order = ["ds"]
    if col_poblacion in serie.columns:
        col_order.append(col_poblacion)
    col_order.append("y_original")
    col_order.append("y")
    serie = serie[col_order]

    # Train/test split
    cutoff_ts = pd.Timestamp(cutoff)
    train_data = serie[serie["ds"] < cutoff_ts].copy().reset_index(drop=True)
    test_data = serie[serie["ds"] >= cutoff_ts].copy().reset_index(drop=True)

    logger.debug(
        "  {} — Train: {} filas | Test: {} filas",
        padecimiento_tipo,
        len(train_data),
        len(test_data),
    )

    return serie, train_data, test_data


def _predecir_test_recursivo(
    xgb: Any,
    yhat_test_prophet: npt.NDArray[np.floating[Any]],
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> npt.NDArray[np.floating[Any]]:
    """Prediccion recursiva XGBoost sobre test sin usar y real del test."""
    y_ext = train_data["y"].values.tolist()
    d_ext = train_data["ds"].values.tolist()
    xgb_adj: list[float] = []

    for i in range(len(test_data)):
        feats = construir_features_xgb(pd.Series(y_ext), pd.Series(pd.to_datetime(d_ext)))
        adj = float(xgb.predict(feats.iloc[[-1]].fillna(0))[0])
        xgb_adj.append(adj)
        # Usar prediccion ensemble como proxy (no el y real del test)
        y_ext.append(float(yhat_test_prophet[i] + adj))
        d_ext.append(test_data["ds"].iloc[i])

    return np.array(xgb_adj)


def generar_predicciones_insample(
    prophet: Any,
    xgb: Any,
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Genera predicciones in-sample (train + test) para graficos.

    Returns:
        (pred_train, pred_test) — DataFrames con columnas ds, yhat_prophet, yhat_ensemble.
    """
    # Prophet in-sample sobre train
    prophet_train = prophet.predict(train_data[["ds"]])
    yhat_train_prophet = prophet_train["yhat"].values

    # XGBoost ajuste sobre train
    feats_train = construir_features_xgb(
        train_data["y"].reset_index(drop=True),
        train_data["ds"].reset_index(drop=True),
    )
    valid_mask = feats_train.notna().all(axis=1)
    xgb_adj_train = np.zeros(len(train_data))
    xgb_adj_train[valid_mask.values] = xgb.predict(feats_train[valid_mask])
    ensemble_train = yhat_train_prophet + xgb_adj_train

    pred_train = pd.DataFrame(
        {
            "ds": train_data["ds"].values,
            "yhat_prophet": yhat_train_prophet,
            "yhat_ensemble": ensemble_train,
        }
    )

    # Prophet + XGBoost sobre test
    pred_test = pd.DataFrame()
    if not test_data.empty:
        prophet_test = prophet.predict(test_data[["ds"]])
        yhat_test_prophet = prophet_test["yhat"].values

        xgb_adj_test = _predecir_test_recursivo(xgb, yhat_test_prophet, train_data, test_data)
        ensemble_test = yhat_test_prophet + xgb_adj_test

        pred_test = pd.DataFrame(
            {
                "ds": test_data["ds"].values,
                "yhat_prophet": yhat_test_prophet,
                "yhat_ensemble": ensemble_test,
            }
        )

    return pred_train, pred_test


def generar_prediccion_completa(
    prophet: Any,
    xgb: Any,
    serie: pd.DataFrame,
    horizon: int = 52,
) -> pd.DataFrame:
    """Genera prediccion historica (in-sample) + futura (out-of-sample).

    Retorna un DataFrame con columnas ds, yhat, yhat_lower, yhat_upper,
    yhat_prophet, yhat_ensemble cubriendo todo el rango de la serie mas
    ``horizon`` semanas adicionales — comportamiento LSP con Prophet.

    Args:
        prophet: Modelo Prophet entrenado.
        xgb: Modelo XGBRegressor entrenado sobre residuos.
        serie: Serie completa (train + test) con columnas ds, y.
        horizon: Semanas de pronostico mas alla de la serie.
    """
    last_train = pd.Timestamp(prophet.history["ds"].max())
    last_real = serie["ds"].max() if not serie.empty else last_train
    weeks_beyond = max(int(np.ceil((last_real - last_train).days / 7)), 0)

    # Prophet sobre todo el rango: historico + test + futuro
    future_df = prophet.make_future_dataframe(periods=weeks_beyond + horizon, freq="W-MON")
    prophet_full = prophet.predict(future_df)

    # --- In-sample (batch): features XGBoost con datos reales ---
    y_series = serie["y"].reset_index(drop=True)
    d_series = serie["ds"].reset_index(drop=True)
    feats_all = construir_features_xgb(y_series, d_series)
    valid = feats_all.notna().all(axis=1)
    xgb_adj_insample = np.zeros(len(serie))
    xgb_adj_insample[valid.values] = xgb.predict(feats_all[valid])

    # Merge con Prophet in-sample
    insample_dates = serie["ds"].values
    prophet_insample = prophet_full[prophet_full["ds"].isin(insample_dates)]
    yhat_prophet_in = prophet_insample["yhat"].values[: len(serie)]
    ensemble_in = yhat_prophet_in + xgb_adj_insample

    rows_insample = pd.DataFrame(
        {
            "ds": insample_dates,
            "yhat": ensemble_in,
            "yhat_lower": ensemble_in,
            "yhat_upper": ensemble_in,
            "yhat_prophet": yhat_prophet_in,
            "yhat_ensemble": ensemble_in,
        }
    )

    # --- Out-of-sample (iterativo): extender con yhat_prophet como proxy ---
    mask_futuro = prophet_full["ds"] > last_real
    future_dates = prophet_full.loc[mask_futuro, "ds"].values
    future_yhat_prophet = prophet_full.loc[mask_futuro, "yhat"].values

    y_ext = serie["y"].values.tolist()
    d_ext = serie["ds"].values.tolist()
    xgb_adj_future: list[float] = []

    for i in range(len(future_dates)):
        feats = construir_features_xgb(pd.Series(y_ext), pd.Series(pd.to_datetime(d_ext)))
        adj = float(xgb.predict(feats.iloc[[-1]].fillna(0))[0])
        xgb_adj_future.append(adj)
        y_ext.append(float(future_yhat_prophet[i]))
        d_ext.append(future_dates[i])

    ensemble_future = future_yhat_prophet + np.array(xgb_adj_future)
    rows_future = pd.DataFrame(
        {
            "ds": future_dates,
            "yhat": ensemble_future,
            "yhat_lower": ensemble_future,
            "yhat_upper": ensemble_future,
            "yhat_prophet": future_yhat_prophet,
            "yhat_ensemble": ensemble_future,
        }
    )

    return pd.concat([rows_insample, rows_future], ignore_index=True)


def calcular_metricas_ensemble(
    test_data: pd.DataFrame,
    pred_test: pd.DataFrame,
    train_data: pd.DataFrame,
    nombre: str,
    tiempo_total: float,
) -> dict[str, Any]:
    """Calcula metricas sobre el test set para el ensemble."""
    if test_data.empty or pred_test.empty:
        return {
            "modelo": nombre,
            "rmse": 0.0,
            "mae": 0.0,
            "smape": 0.0,
            "mase": None,
            "tiempo": tiempo_total,
        }

    y_true = test_data["y"].to_numpy(dtype=float)
    y_pred = pred_test["yhat_ensemble"].to_numpy(dtype=float)
    y_train = train_data["y"].to_numpy(dtype=float)
    metrics = compute_forecast_metrics(y_true, y_pred, y_train)

    return {
        "modelo": nombre,
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "smape": metrics["smape"],
        "mase": metrics["mase"],
        "tiempo": tiempo_total,
    }


def calcular_metricas_prophet_base(
    test_data: pd.DataFrame,
    pred_test: pd.DataFrame,
    train_data: pd.DataFrame,
    t_prophet: float,
) -> dict[str, Any]:
    """Metricas del Prophet base solo (sin XGBoost) sobre test set."""
    if test_data.empty or pred_test.empty:
        return {
            "modelo": "Prophet Base",
            "rmse": 0.0,
            "mae": 0.0,
            "smape": 0.0,
            "mase": None,
            "tiempo": 0.0,
        }

    y_true = test_data["y"].to_numpy(dtype=float)
    y_pred = pred_test["yhat_prophet"].to_numpy(dtype=float)
    y_train = train_data["y"].to_numpy(dtype=float)
    metrics = compute_forecast_metrics(y_true, y_pred, y_train)

    return {
        "modelo": "Prophet Base",
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "smape": metrics["smape"],
        "mase": metrics["mase"],
        "tiempo": t_prophet,
    }
