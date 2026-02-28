# src/epiforecast/models/ensemble/helpers.py
"""Ensemble helper functions: feature engineering, data preparation, metrics.

Extracted from model.py for SRP compliance (max 300 lines per module).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.config import logger

# Features que construye XGBoost
FEATURE_NAMES: list[str] = [
    "lag_1",
    "lag_2",
    "lag_4",
    "roll_4",
    "roll_8",
    "roll_12",
    "month",
    "week_of_year",
]


def construir_features_xgb(y_series: pd.Series, dates: pd.Series) -> pd.DataFrame:
    """Construye features temporales y de lags para XGBoost."""
    feats = pd.DataFrame(index=y_series.index)
    feats["lag_1"] = y_series.shift(1)
    feats["lag_2"] = y_series.shift(2)
    feats["lag_4"] = y_series.shift(4)
    feats["roll_4"] = y_series.rolling(4).mean()
    feats["roll_8"] = y_series.rolling(8).mean()
    feats["roll_12"] = y_series.rolling(12).mean()
    feats["month"] = dates.dt.month
    feats["week_of_year"] = dates.dt.isocalendar().week.astype(int).values
    return feats


def construir_holidays(config: dict[str, Any]) -> pd.DataFrame:
    """Construye DataFrame de holidays desde config (periodos atipicos)."""
    periodos = config.get("peridos_atipicos", [])
    if not periodos:
        return pd.DataFrame(columns=["holiday", "ds", "lower_window", "upper_window"])

    rows = []
    for p in periodos:
        rows.append(
            {
                "holiday": p["holiday"],
                "ds": pd.Timestamp(p["ds"]),
                "lower_window": p.get("lower_window", 0),
                "upper_window": p.get("upper_window", 0),
            }
        )
    return pd.DataFrame(rows)


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
    if sexo in df_filtrado.columns:
        serie = (
            df_filtrado.groupby(col_fecha, as_index=False)[[sexo]]
            .sum()
            .rename(columns={col_fecha: "ds", sexo: "y"})
            .sort_values("ds")
            .reset_index(drop=True)
        )
    elif "y" in df_filtrado.columns and "ds" in df_filtrado.columns:
        serie = df_filtrado[["ds", "y"]].copy().sort_values("ds").reset_index(drop=True)
    else:
        raise ValueError(
            f"No se encontro columna '{sexo}' ni 'y' en el DataFrame. "
            f"Columnas: {list(df_filtrado.columns)}"
        )

    # Train/test split
    cutoff_ts = pd.Timestamp(cutoff)
    train_data = serie[serie["ds"] < cutoff_ts].copy().reset_index(drop=True)
    test_data = serie[serie["ds"] >= cutoff_ts].copy().reset_index(drop=True)

    logger.info(
        "  {} — Train: {} filas | Test: {} filas",
        padecimiento_tipo,
        len(train_data),
        len(test_data),
    )

    return serie, train_data, test_data


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

        full_y = pd.concat([train_data["y"], test_data["y"]], ignore_index=True)
        full_dates = pd.concat([train_data["ds"], test_data["ds"]], ignore_index=True)
        feats_full = construir_features_xgb(full_y, full_dates)
        feats_test = feats_full.iloc[len(train_data) :].fillna(0)

        xgb_adj_test = xgb.predict(feats_test)
        ensemble_test = yhat_test_prophet + xgb_adj_test

        pred_test = pd.DataFrame(
            {
                "ds": test_data["ds"].values,
                "yhat_prophet": yhat_test_prophet,
                "yhat_ensemble": ensemble_test,
            }
        )

    return pred_train, pred_test


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
