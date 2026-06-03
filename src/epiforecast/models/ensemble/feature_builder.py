"""XGBoost feature engineering for the Ensemble model.

Extracted from helpers.py for SRP compliance (max 300 lines per module).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.constants import COVID_END, COVID_START
from epiforecast.utils.cohorts import is_neuro

__all__ = ["FEATURE_NAMES", "construir_features_xgb", "construir_holidays"]

# Features que construye XGBoost (20 total)
FEATURE_NAMES: list[str] = [
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_8",
    "lag_13",
    "lag_26",
    "lag_52",
    "roll_4",
    "roll_8",
    "roll_12",
    "roll_26",
    "roll_52",
    "roll_std_13",
    "month",
    "week_of_year",
    "sin_week",
    "cos_week",
    "roc_4",
    "roc_52",
    "covid_flag",
]


def construir_features_xgb(y_series: pd.Series, dates: pd.Series) -> pd.DataFrame:
    """Construye features temporales y de lags para XGBoost (20 features)."""
    feats = pd.DataFrame(index=y_series.index)

    # Lags
    feats["lag_1"] = y_series.shift(1)
    feats["lag_2"] = y_series.shift(2)
    feats["lag_4"] = y_series.shift(4)
    feats["lag_8"] = y_series.shift(8)
    feats["lag_13"] = y_series.shift(13)
    feats["lag_26"] = y_series.shift(26)
    feats["lag_52"] = y_series.shift(52)

    # Rolling means (sobre shifted para evitar data leakage)
    shifted = y_series.shift(1)
    feats["roll_4"] = shifted.rolling(4).mean()
    feats["roll_8"] = shifted.rolling(8).mean()
    feats["roll_12"] = shifted.rolling(12).mean()
    feats["roll_26"] = shifted.rolling(26).mean()
    feats["roll_52"] = shifted.rolling(52).mean()

    # Volatilidad trimestral
    feats["roll_std_13"] = shifted.rolling(13).std()

    # Calendario
    feats["month"] = dates.dt.month
    week_vals = dates.dt.isocalendar().week.astype(int).values
    feats["week_of_year"] = week_vals

    # Codificacion ciclica de semana
    feats["sin_week"] = np.sin(2 * np.pi * week_vals / 52)
    feats["cos_week"] = np.cos(2 * np.pi * week_vals / 52)

    # Tasa de cambio sobre shifted (evitar leakage: no usar y[t] como feature)
    feats["roc_4"] = shifted.pct_change(3).replace([np.inf, -np.inf], np.nan)
    feats["roc_52"] = shifted.pct_change(51).replace([np.inf, -np.inf], np.nan)

    # COVID flag
    covid_start = pd.Timestamp(COVID_START)
    covid_end = pd.Timestamp(COVID_END)
    dt_dates = pd.to_datetime(dates)
    feats["covid_flag"] = ((dt_dates >= covid_start) & (dt_dates <= covid_end)).astype(int).values

    # Limpiar cualquier inf residual (seguridad contra division por cero)
    feats.replace([np.inf, -np.inf], np.nan, inplace=True)

    return feats


def construir_holidays(config: dict[str, Any], padecimiento: str | None = None) -> pd.DataFrame:
    """Construye DataFrame de holidays desde config (periodos atipicos).

    Cohort-aware: los padecimientos fuera de la cohorte neuro (p.ej. Dengue) NO usan los
    periodos atípicos (holiday COVID), igual que en el motor Prophet. Si ``padecimiento``
    es ``None`` (desconocido) se mantiene el comportamiento histórico (incluye COVID).
    """
    empty = pd.DataFrame(columns=["holiday", "ds", "lower_window", "upper_window"])
    if padecimiento is not None and not is_neuro(padecimiento):
        return empty
    periodos = config.get("peridos_atipicos", [])
    if not periodos:
        return empty

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
