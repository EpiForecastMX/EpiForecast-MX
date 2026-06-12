# src/epiforecast/visualization/comparison_builders.py
"""Pure rendering functions for model comparison charts.

Each builder receives DataFrames + config and returns a matplotlib Figure.
No I/O (no file loading, no saving). Las primitivas de panel viven en
``comparison_panels`` y los builders de metricas/residuales en ``comparison_metrics``
(re-exportados aqui por compatibilidad).
"""

from __future__ import annotations

import matplotlib.dates as mdates
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.visualization import chart_constants as cc
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    COLOR_REAL_OVERLAY,
    MODEL_STYLES,
)
from epiforecast.visualization.comparison_metrics import (
    build_metrics_bars,
    build_residuals,
)
from epiforecast.visualization.comparison_panels import (
    _add_covid_band,
    _add_cutoff_line,
    _add_cv_zone,
    _add_forecast_band,
    _stamp,
    _suptitle,
)

# API publico: los 4 builders de comparacion. `build_metrics_bars` y
# `build_residuals` se re-exportan desde `comparison_metrics` por compatibilidad.
__all__ = [
    "build_metrics_bars",
    "build_overlay",
    "build_residuals",
    "build_small_multiples",
]

# ---------------------------------------------------------------------------
# 1. Small Multiples (2x2)
# ---------------------------------------------------------------------------


def _extract_panel_metrics(pred_df: pd.DataFrame) -> dict[str, float] | None:
    """Extract SMAPE, MASE, RMSE, MAE, MAPE from forecast metadata for a panel."""
    required = ("smape_usado", "mase_usado", "rmse_usado", "mae_usado")
    if not all(c in pred_df.columns for c in required):
        return None
    row = pred_df.iloc[0]
    # SMAPE is mandatory for production model selection
    if pd.isna(row["smape_usado"]):
        return None
    result: dict[str, float] = {}
    for col in (*required, "mape_usado"):
        key = col.replace("_usado", "").upper()
        val = row.get(col)
        result[key] = float(val) if not pd.isna(val) else float("nan")
    return result


def _find_prod_model(metrics_by_model: dict[str, dict[str, float]]) -> str | None:
    """Determine production model: lowest SMAPE, tiebreak MASE, then RMSE."""
    if not metrics_by_model:
        return None
    candidates = [(k, m) for k, m in metrics_by_model.items() if "SMAPE" in m]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[1]["SMAPE"], x[1].get("MASE", 99), x[1].get("RMSE", 99)))
    return candidates[0][0]


def _prod_justification(prod_key: str, metrics_by_model: dict[str, dict[str, float]]) -> str:
    """Brief justification for why this model is the production choice."""
    m = metrics_by_model[prod_key]
    parts = [f"SMAPE {m['SMAPE']:.2f}%"]
    mase = m.get("MASE", 99.0)
    if mase < 1.0:
        parts.append(f"MASE {mase:.2f} (supera naive)")
    else:
        parts.append(f"MASE {mase:.2f}")
    return "Mejor: " + ", ".join(parts)


def build_small_multiples(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure:
    """2x2 grid: each model in its own subplot with metrics and production highlight."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), sharex=False, sharey=True)
    cutoff = serie_real["ds"].max()

    # Smoothed real data (same rolling window as individual panels)
    serie_sorted = serie_real.sort_values("ds")
    y_smooth = (
        target_y.iloc[serie_sorted.index]
        .rolling(cc.ROLLING_OBS, min_periods=1, center=True)
        .mean()
    )

    # IQR outlier detection (same as individual panels)
    q1 = target_y.quantile(0.25)
    q3 = target_y.quantile(0.75)
    iqr = q3 - q1
    outlier_mask = (target_y < q1 - 1.5 * iqr) | (target_y > q3 + 1.5 * iqr)
    outlier_ds = serie_real.loc[outlier_mask, "ds"]
    outlier_y = target_y[outlier_mask]

    # Extract metrics per model and find production model
    metrics_by_model: dict[str, dict[str, float]] = {}
    for model_key in MODEL_STYLES:
        if model_key in predictions:
            m = _extract_panel_metrics(predictions[model_key])
            if m:
                metrics_by_model[model_key] = m
    prod_key = _find_prod_model(metrics_by_model)

    for model_key, style in MODEL_STYLES.items():
        r, c = style.grid_pos
        ax = axes[r, c]

        # Forecast zone background
        if model_key in predictions:
            grp = predictions[model_key]
            fecha_max_fc = grp["ds"].max()
            ax.axvspan(
                cutoff,
                fecha_max_fc,
                alpha=cc.ALPHA_FORECAST_ZONE,
                color=style.color,
                zorder=0,
            )

        # Contextual layers
        _add_covid_band(ax, compact=True)
        _add_cv_zone(ax, cutoff, compact=True)

        # Smoothed real data
        ax.plot(
            serie_sorted["ds"],
            y_smooth,
            color="#2C2C2C",
            linewidth=1.5,
            alpha=1.0,
            label="Real",
            zorder=5,
        )

        # Outlier markers
        if len(outlier_ds) > 0:
            ax.scatter(
                outlier_ds,
                outlier_y,
                marker="^",
                s=30,
                color=COLOR_CUTOFF,
                edgecolors="white",
                linewidths=0.5,
                zorder=5,
            )

        # Model: backtesting (historical) + future split
        if model_key in predictions:
            grp = predictions[model_key]
            overlap = grp[grp["ds"] <= cutoff]
            future = grp[grp["ds"] > cutoff]

            if not overlap.empty:
                ax.plot(
                    overlap["ds"],
                    overlap["yhat"],
                    color=style.color,
                    linewidth=1.2,
                    alpha=0.50,
                    zorder=3,
                    label="Ajuste",
                )
            if not future.empty:
                ax.plot(
                    future["ds"],
                    future["yhat"],
                    color=style.color,
                    linewidth=1.8,
                    alpha=0.85,
                    zorder=3,
                    label="Pronostico",
                )

            # 80% confidence band
            _add_forecast_band(ax, grp, cutoff, style.color)

        _add_cutoff_line(ax, cutoff, compact=True)

        # -- Year ticks on all 4 subplots --
        ax.xaxis.set_major_locator(mdates.YearLocator())  # type: ignore[no-untyped-call]
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))  # type: ignore[no-untyped-call]
        ax.tick_params(axis="x", labelsize=8, rotation=0)

        # -- Title with PROD tag for production model --
        is_prod = model_key == prod_key
        title_prefix = "PROD  " if is_prod else ""
        ax.set_title(
            f"{title_prefix}{style.label}",
            fontweight="bold",
            fontsize=11,
            color="#B8860B" if is_prod else "black",
        )

        # -- Golden border (single, clean) for production model --
        if is_prod:
            for spine in ax.spines.values():
                spine.set_edgecolor("#DAA520")
                spine.set_linewidth(2.5)
                spine.set_visible(True)
        else:
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)

        ax.legend(fontsize=7, loc="upper left", framealpha=0.8)
        ax.grid(
            True,
            color="lightgrey",
            linestyle="--",
            linewidth=0.5,
            alpha=cc.ALPHA_GRID,
        )

        # -- Horizontal metrics bar below x-axis --
        if model_key in metrics_by_model:
            m = metrics_by_model[model_key]
            parts = [f"SMAPE {m['SMAPE']:.2f}%"]
            mase_val = m.get("MASE", float("nan"))
            if not np.isnan(mase_val):
                mase_star = "*" if mase_val < 1.0 else ""
                parts.append(f"MASE {mase_val:.2f}{mase_star}")
            parts.append(f"RMSE {m['RMSE']:.2f}")
            parts.append(f"MAE {m['MAE']:.2f}")
            mape_val = m.get("MAPE", float("nan"))
            if not np.isnan(mape_val):
                parts.append(f"MAPE {mape_val:.2f}%")
            metrics_line = "  |  ".join(parts)

            bar_color = "#B8860B" if is_prod else "#666666"
            ax.text(
                0.5,
                -0.10,
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

        ax.set_xlabel("", fontsize=10)
        if c == 0:
            ax.set_ylabel("Casos Semanales", fontsize=10)

    # -- Suptitle + production justification banner --
    ent_display = ent if ent else "Nacional"
    fig.suptitle(
        f"Paneles Individuales: {pad} - {ent_display} ({modo})",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )

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
# 2. Overlay completo
# ---------------------------------------------------------------------------


def build_overlay(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure:
    """All model series overlaid on a single panel."""
    fig, ax = plt.subplots(figsize=(14, 6))
    cutoff = serie_real["ds"].max()

    # Smoothed real data
    serie_sorted = serie_real.sort_values("ds")
    y_smooth = (
        target_y.iloc[serie_sorted.index]
        .rolling(cc.ROLLING_OBS, min_periods=1, center=True)
        .mean()
    )

    ax.plot(
        serie_sorted["ds"],
        y_smooth,
        color=COLOR_REAL_OVERLAY,
        linewidth=2,
        label="Historial Real",
        zorder=1,
    )

    # Models
    for model_key, style in MODEL_STYLES.items():
        if model_key not in predictions:
            continue
        grp = predictions[model_key]
        ax.plot(
            grp["ds"],
            grp["yhat"],
            color=style.color,
            linewidth=1.5,
            label=style.label,
            zorder=3,
        )

    _add_covid_band(ax)
    _add_cv_zone(ax, cutoff)
    _add_cutoff_line(ax, cutoff)

    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        fontsize=9,
        frameon=True,
    )
    ax.set_ylabel("Casos Semanales", fontsize=11)
    ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=cc.ALPHA_GRID)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    _suptitle(fig, "Overlay Completo", pad, ent, modo)
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 0.85, 0.95))
    return fig
