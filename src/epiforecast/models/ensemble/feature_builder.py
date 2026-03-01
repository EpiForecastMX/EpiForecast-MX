"""XGBoost feature engineering for the Ensemble model.

Extracted from helpers.py for SRP compliance (max 300 lines per module).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

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
