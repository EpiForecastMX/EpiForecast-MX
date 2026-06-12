# src/epiforecast/visualization/comparison_bars_helpers.py
"""Helpers para las barras semanales de comparacion (escala, preparacion de
barras, ticks mensuales, ficha tecnica). Sin I/O."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from matplotlib.figure import Figure
import numpy as np
import pandas as pd

_TZ_CDMX = ZoneInfo("America/Mexico_City")
_N_WEEKS = 52
_MESES_ES = [
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_scale(y_real_median: float, yhat_hist_median: float) -> float:
    """Return scale factor when yhat is on a normalised (rate) scale."""
    if y_real_median <= 0 or yhat_hist_median <= 0:
        return 1.0
    ratio = yhat_hist_median / y_real_median
    if ratio < 0.1:
        return y_real_median / yhat_hist_median
    return 1.0


def _prepare_bars(
    serie_real: pd.DataFrame,
    pred: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Return (hist_df, future_df, scale).

    hist_df:  last 52 weeks with columns ds, y_real, yhat, yhat_lower, yhat_upper.
    future_df: next 52 weeks with columns ds, yhat, yhat_lower, yhat_upper.
    """
    target_col = "y_original" if "y_original" in serie_real.columns else "y"
    real = serie_real[["ds", target_col]].rename(columns={target_col: "y_real"}).copy()
    real = real.sort_values("ds").tail(_N_WEEKS).reset_index(drop=True)

    pred_sorted = pred.sort_values("ds")
    hist_pred = pred_sorted[pred_sorted["ds"] <= cutoff].tail(_N_WEEKS)
    future_pred = pred_sorted[pred_sorted["ds"] > cutoff].head(_N_WEEKS)

    # Merge real + hist prediction
    hist_df = real.merge(
        hist_pred[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(
            columns={"yhat_lower": "yhat_lower", "yhat_upper": "yhat_upper"}
        ),
        on="ds",
        how="left",
    )

    # Detect scale
    y_med = float(hist_df["y_real"].median()) if not hist_df.empty else 1.0
    yhat_med = float(hist_df["yhat"].median()) if not hist_df["yhat"].isna().all() else 1.0
    scale = _detect_scale(y_med, yhat_med)

    # Apply scale and clamp
    for col in ("yhat", "yhat_lower", "yhat_upper"):
        if col in hist_df.columns:
            hist_df[col] = np.maximum(hist_df[col].fillna(0) * scale, 0)

    future_df = future_pred[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    for col in ("yhat", "yhat_lower", "yhat_upper"):
        if col in future_df.columns:
            future_df[col] = np.maximum(future_df[col].fillna(0) * scale, 0)

    return hist_df.reset_index(drop=True), future_df.reset_index(drop=True), scale


def _month_ticks(
    dates_hist: pd.Series,
    dates_future: pd.Series,
) -> tuple[list[float], list[str]]:
    """Generate monthly tick positions and Spanish labels for 104 bars."""
    all_dates = pd.concat([dates_hist, dates_future], ignore_index=True)
    positions: list[float] = []
    labels: list[str] = []
    last_label = ""
    for i, d in enumerate(all_dates):
        ts = pd.Timestamp(d)
        lbl = f"{_MESES_ES[ts.month - 1]}'{str(ts.year)[-2:]}"
        if lbl != last_label:
            positions.append(float(i))
            labels.append(lbl)
            last_label = lbl
    return positions, labels


def _stamp(fig: Figure) -> None:
    """Add CDMX timestamp footer."""
    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5,
        0.01,
        f"Generado: {ahora} CDMX  |  EpiForecast-MX",
        ha="center",
        fontsize=8,
        color="#808080",
        style="italic",
    )


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
