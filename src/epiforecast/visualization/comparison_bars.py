# src/epiforecast/visualization/comparison_bars.py
"""Pure builder for weekly bar charts: 52 hist (real vs ajuste) + 52 future.

Each panel in a 2x2 grid shows paired bars for the historical zone and
single bars with CI whiskers for the forecast zone.  No I/O.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.visualization.comparison_builders import (
    _extract_panel_metrics,
    _find_prod_model,
    _prod_justification,
)
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    MODEL_STYLES,
)

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


def build_weekly_bars(
    serie_real: pd.DataFrame,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure:
    """Build a 2x2 figure with weekly bar panels (52 hist + 52 future).

    Parameters
    ----------
    serie_real : DataFrame with ds, y_original (or y), Total columns.
    predictions : {model_key: forecast_df} with ds, yhat, yhat_lower, yhat_upper.
    pad, ent, modo : metadata for titles.
    """
    fig, axes = plt.subplots(2, 2, figsize=(20, 13))
    cutoff = serie_real["ds"].max()

    # Metrics & production model
    metrics_by_model: dict[str, dict[str, float]] = {}
    for mk in MODEL_STYLES:
        if mk in predictions:
            m = _extract_panel_metrics(predictions[mk])
            if m:
                metrics_by_model[mk] = m
    prod_key = _find_prod_model(metrics_by_model)

    for model_key, style in MODEL_STYLES.items():
        r, c = style.grid_pos
        ax = axes[r, c]

        if model_key not in predictions:
            ax.set_title(f"{style.label} (sin datos)", fontsize=11)
            ax.text(
                0.5,
                0.5,
                "Sin forecast",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=12,
                color="#999",
            )
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            continue

        hist_df, future_df, _sc = _prepare_bars(
            serie_real,
            predictions[model_key],
            cutoff,
        )

        n_hist = len(hist_df)
        n_fut = len(future_df)
        x_hist = np.arange(n_hist)
        x_fut = np.arange(n_hist, n_hist + n_fut)

        # -- Month alternation bands --
        all_dates = pd.concat(
            [hist_df["ds"], future_df["ds"]],
            ignore_index=True,
        )
        prev_month = -1
        band_on = False
        for i, d in enumerate(all_dates):
            mo = pd.Timestamp(d).month
            if mo != prev_month:
                band_on = not band_on
                prev_month = mo
            if band_on:
                ax.axvspan(i - 0.5, i + 0.5, alpha=0.04, color="#888888", zorder=0)

        # -- Historical bars: paired real (grey) + ajuste (color) --
        bar_w_hist = 0.38
        ax.bar(
            x_hist - bar_w_hist / 2,
            hist_df["y_real"].values,
            width=bar_w_hist,
            color="#616161",
            alpha=0.85,
            label="Real",
            zorder=3,
        )
        if not hist_df["yhat"].isna().all():
            ax.bar(
                x_hist + bar_w_hist / 2,
                hist_df["yhat"].values,
                width=bar_w_hist,
                color=style.color,
                alpha=0.55,
                label="Ajuste",
                zorder=3,
            )

        # -- Future bars: single with whiskers --
        if not future_df.empty:
            yhat_vals = np.asarray(future_df["yhat"].values)
            lower = np.asarray(future_df["yhat_lower"].values)
            upper = np.asarray(future_df["yhat_upper"].values)
            yerr_lo = np.maximum(yhat_vals - lower, 0)
            yerr_hi = np.maximum(upper - yhat_vals, 0)
            ax.bar(
                x_fut,
                yhat_vals,
                width=0.70,
                color=style.color,
                alpha=0.85,
                label="Pronostico",
                zorder=3,
                yerr=[yerr_lo, yerr_hi],
                error_kw=dict(capsize=1, lw=0.6, color="#444444"),
            )

        # -- Cutoff line --
        ax.axvline(
            n_hist - 0.5,
            color=COLOR_CUTOFF,
            linestyle="--",
            linewidth=1.2,
            alpha=0.7,
            zorder=7,
        )

        # -- X ticks (monthly) --
        positions, labels = _month_ticks(hist_df["ds"], future_df["ds"])
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=6.5, rotation=45, ha="right")

        # -- Grid: horizontal only --
        ax.grid(axis="y", color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)
        ax.set_axisbelow(True)

        # -- Title + production highlight --
        is_prod = model_key == prod_key
        title_prefix = "PROD  " if is_prod else ""
        ax.set_title(
            f"{title_prefix}{style.label}",
            fontweight="bold",
            fontsize=11,
            color="#B8860B" if is_prod else "black",
        )
        if is_prod:
            for spine in ax.spines.values():
                spine.set_edgecolor("#DAA520")
                spine.set_linewidth(2.5)
                spine.set_visible(True)
        else:
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)

        # -- Legend --
        ax.legend(fontsize=7, loc="upper left", framealpha=0.8)

        # -- Y label --
        if c == 0:
            ax.set_ylabel("Casos semanales", fontsize=10)

        # -- Metrics bar --
        if model_key in metrics_by_model:
            m = metrics_by_model[model_key]
            parts = [f"SMAPE {m['SMAPE']:.2f}%"]
            mase_val = m.get("MASE", float("nan"))
            if not np.isnan(mase_val):
                mase_star = "*" if mase_val < 1.0 else ""
                parts.append(f"MASE {mase_val:.2f}{mase_star}")
            parts.append(f"RMSE {m['RMSE']:.2f}")
            parts.append(f"MAE {m['MAE']:.2f}")
            metrics_line = "  |  ".join(parts)
            bar_color = "#B8860B" if is_prod else "#666666"
            ax.text(
                0.5,
                -0.12,
                metrics_line,
                transform=ax.transAxes,
                fontsize=7,
                fontfamily="monospace",
                fontweight="bold" if is_prod else "normal",
                color=bar_color,
                ha="center",
                va="top",
                zorder=10,
            )

    # -- Suptitle --
    ent_display = ent if ent else "Nacional"
    fig.suptitle(
        f"Barras semanales: {pad} - {ent_display} ({modo})",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )

    # -- Production banner --
    if prod_key and prod_key in metrics_by_model:
        justification = _prod_justification(prod_key, metrics_by_model)
        prod_label = MODEL_STYLES[prod_key].label
        fig.text(
            0.5,
            0.955,
            f"Modelo de produccion: {prod_label}  --  {justification}",
            ha="center",
            fontsize=9,
            fontstyle="italic",
            color="#B8860B",
            fontweight="bold",
        )

    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    return fig


# ---------------------------------------------------------------------------
# Single-panel builder (production model only)
# ---------------------------------------------------------------------------


def build_single_prod_bars(
    serie_real: pd.DataFrame,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure | None:
    """Build a single elongated panel showing only the winning model.

    Returns ``None`` when no production model can be determined (e.g. all
    forecasts lack metrics).

    Parameters
    ----------
    serie_real : DataFrame with ds, y_original (or y).
    predictions : {model_key: forecast_df} with ds, yhat, yhat_lower, yhat_upper.
    pad, ent, modo : metadata for titles.
    """
    cutoff = serie_real["ds"].max()

    # --- Determine production model ---
    metrics_by_model: dict[str, dict[str, float]] = {}
    for mk in MODEL_STYLES:
        if mk in predictions:
            m = _extract_panel_metrics(predictions[mk])
            if m:
                metrics_by_model[mk] = m
    prod_key = _find_prod_model(metrics_by_model)
    if prod_key is None or prod_key not in predictions:
        return None

    style = MODEL_STYLES[prod_key]

    # --- Prepare data ---
    hist_df, future_df, _sc = _prepare_bars(
        serie_real,
        predictions[prod_key],
        cutoff,
    )

    n_hist = len(hist_df)
    n_fut = len(future_df)
    x_hist = np.arange(n_hist)
    x_fut = np.arange(n_hist, n_hist + n_fut)

    # --- Figure ---
    fig, ax = plt.subplots(figsize=(26, 5.5))

    # Month alternation bands
    all_dates = pd.concat(
        [hist_df["ds"], future_df["ds"]],
        ignore_index=True,
    )
    prev_month = -1
    band_on = False
    for i, d in enumerate(all_dates):
        mo = pd.Timestamp(d).month
        if mo != prev_month:
            band_on = not band_on
            prev_month = mo
        if band_on:
            ax.axvspan(i - 0.5, i + 0.5, alpha=0.04, color="#888888", zorder=0)

    # Historical bars: paired real (grey) + ajuste (color)
    bar_w = 0.38
    ax.bar(
        x_hist - bar_w / 2,
        np.asarray(hist_df["y_real"].values),
        width=bar_w,
        color="#616161",
        alpha=0.85,
        label="Real",
        zorder=3,
    )
    if not hist_df["yhat"].isna().all():
        ax.bar(
            x_hist + bar_w / 2,
            np.asarray(hist_df["yhat"].values),
            width=bar_w,
            color=style.color,
            alpha=0.55,
            label="Ajuste",
            zorder=3,
        )

    # Future bars with whiskers
    if not future_df.empty:
        yhat_vals = np.asarray(future_df["yhat"].values)
        lower = np.asarray(future_df["yhat_lower"].values)
        upper = np.asarray(future_df["yhat_upper"].values)
        yerr_lo = np.maximum(yhat_vals - lower, 0)
        yerr_hi = np.maximum(upper - yhat_vals, 0)
        ax.bar(
            x_fut,
            yhat_vals,
            width=0.70,
            color=style.color,
            alpha=0.85,
            label="Pronostico",
            zorder=3,
            yerr=[yerr_lo, yerr_hi],
            error_kw=dict(capsize=1, lw=0.6, color="#444444"),
        )

    # Cutoff line
    ax.axvline(
        n_hist - 0.5,
        color=COLOR_CUTOFF,
        linestyle="--",
        linewidth=1.2,
        alpha=0.7,
        zorder=7,
    )

    # X ticks (monthly)
    positions, labels = _month_ticks(hist_df["ds"], future_df["ds"])
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")

    # Grid
    ax.grid(axis="y", color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.set_ylabel("Casos semanales", fontsize=10)

    # Golden border
    for spine in ax.spines.values():
        spine.set_edgecolor("#DAA520")
        spine.set_linewidth(2.5)
        spine.set_visible(True)

    ax.legend(fontsize=8, loc="upper left", framealpha=0.8)

    # --- Metrics bar ---
    if prod_key in metrics_by_model:
        m = metrics_by_model[prod_key]
        parts = [f"SMAPE {m['SMAPE']:.2f}%"]
        mase_val = m.get("MASE", float("nan"))
        if not np.isnan(mase_val):
            mase_star = "*" if mase_val < 1.0 else ""
            parts.append(f"MASE {mase_val:.2f}{mase_star}")
        parts.append(f"RMSE {m['RMSE']:.2f}")
        parts.append(f"MAE {m['MAE']:.2f}")
        metrics_line = "  |  ".join(parts)
        ax.text(
            0.5,
            -0.10,
            metrics_line,
            transform=ax.transAxes,
            fontsize=8,
            fontfamily="monospace",
            fontweight="bold",
            color="#B8860B",
            ha="center",
            va="top",
            zorder=10,
        )

    # --- Title ---
    ent_display = ent if ent else "Nacional"
    justification = _prod_justification(prod_key, metrics_by_model)
    fig.suptitle(
        f"{pad} - {ent_display} ({modo})  |  Modelo: {style.label}  --  {justification}",
        fontsize=13,
        fontweight="bold",
        y=0.98,
        color="#B8860B",
    )

    _stamp(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    return fig
