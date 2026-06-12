# src/epiforecast/visualization/comparison_prod_bars.py
"""Builder del panel unico del modelo productivo ganador (barras). Sin I/O."""

from __future__ import annotations

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.visualization.comparison_bars_helpers import (
    _month_ticks,
    _prepare_bars,
    _stamp,
)
from epiforecast.visualization.comparison_builders import (
    _extract_panel_metrics,
    _find_prod_model,
    _prod_justification,
)
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    MODEL_STYLES,
)


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
