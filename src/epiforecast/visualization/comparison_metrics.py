# src/epiforecast/visualization/comparison_metrics.py
"""Builders de metricas (barras CV) y residuales de la comparacion de modelos."""

from __future__ import annotations

from typing import cast

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.constants import (
    RATE_PER,
)
from epiforecast.visualization import chart_constants as cc
from epiforecast.visualization.comparison_config import (
    MODEL_STYLES,
)
from epiforecast.visualization.comparison_panels import (
    _add_covid_band,
    _merge_real_pred,
    _stamp,
    _suptitle,
)

# ---------------------------------------------------------------------------
# 3. Metricas (barras + tabla)
# ---------------------------------------------------------------------------


def _extract_cv_metrics(pred_df: pd.DataFrame) -> tuple[float, float, float] | None:
    """Extract pre-computed CV metrics (RMSE, MAE, SMAPE) from forecast metadata."""
    cols = ("rmse_usado", "mae_usado", "smape_usado")
    if not all(c in pred_df.columns for c in cols):
        return None
    row = pred_df.iloc[0]
    vals = [row[c] for c in cols]
    if any(pd.isna(v) for v in vals):
        return None
    return (float(vals[0]), float(vals[1]), float(vals[2]))


def _needs_metric_scaling(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    pred_df: pd.DataFrame,
) -> bool:
    """Detect models whose CV metrics are on a normalized scale (yhat == y_real in-sample)."""
    merged = _merge_real_pred(serie_real, target_y, pred_df)
    if merged.empty:
        return False
    residual = merged["y_real"].to_numpy() - merged["yhat"].to_numpy()
    return bool(np.allclose(residual, 0, atol=1e-6))


def build_metrics_bars(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure | None:
    """Grouped bar chart (RMSE / MAE / SMAPE) per model with a summary table.

    Uses pre-computed cross-validation metrics from the forecast CSV metadata.
    For models whose metrics are on a normalized scale (e.g. DeepAR), RMSE and
    MAE are rescaled to absolute cases using Total / RATE_PER.
    """
    metric_names = ["RMSE", "MAE", "SMAPE"]
    rows: list[dict[str, object]] = []

    # Scale factor to convert rate-based metrics to absolute cases
    scale = 1.0
    if "Total" in serie_real.columns:
        scale = float(serie_real["Total"].iloc[0]) / RATE_PER

    for model_key, style in MODEL_STYLES.items():
        if model_key not in predictions:
            continue
        cv = _extract_cv_metrics(predictions[model_key])
        if cv is None:
            continue
        cv_rmse, cv_mae, cv_smape = cv

        if _needs_metric_scaling(serie_real, target_y, predictions[model_key]) and scale > 1:
            cv_rmse *= scale
            cv_mae *= scale

        rows.append(
            {
                "model": style.label,
                "color": style.color,
                "values": [cv_rmse, cv_mae, cv_smape],
            }
        )

    if not rows:
        return None

    fig, (ax_bar, ax_tbl) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # -- Bars --
    n_models = len(rows)
    n_metrics = len(metric_names)
    x = np.arange(n_metrics)
    width = 0.8 / n_models

    for i, row in enumerate(rows):
        offset = (i - n_models / 2 + 0.5) * width
        ax_bar.bar(
            x + offset,
            row["values"],
            width,
            label=row["model"],
            color=row["color"],
            alpha=0.85,
        )

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(metric_names, fontsize=11)
    ax_bar.set_ylabel("Valor", fontsize=11)
    ax_bar.legend(fontsize=9)
    ax_bar.grid(axis="y", color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)
    for spine in ("top", "right"):
        ax_bar.spines[spine].set_visible(False)

    # -- Table --
    cell_text = []
    row_labels = []
    for row in rows:
        row_labels.append(str(row["model"]))
        vals = cast(list[float], row["values"])
        cell_text.append([f"{v:.2f}" for v in vals])
    row_colors = [str(r["color"]) for r in rows]

    ax_tbl.axis("off")
    table = ax_tbl.table(
        cellText=cell_text,
        rowLabels=row_labels,
        colLabels=metric_names,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.4)

    # Color row labels
    for i, color in enumerate(row_colors):
        table[i + 1, -1].set_facecolor(color)
        table[i + 1, -1].set_text_props(color="white", fontweight="bold")
    _suptitle(fig, "Metricas de Validacion Cruzada", pad, ent, modo)
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig


# ---------------------------------------------------------------------------
# 4. Residuales (2x2)
# ---------------------------------------------------------------------------


def build_residuals(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    predictions: dict[str, pd.DataFrame],
    pad: str,
    ent: str,
    modo: str,
) -> Figure:
    """2x2 residual plot (y_real - yhat) per model with colored fill."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)

    for model_key, style in MODEL_STYLES.items():
        r, c = style.grid_pos
        ax = axes[r, c]

        if model_key in predictions:
            merged = _merge_real_pred(serie_real, target_y, predictions[model_key])
            if not merged.empty:
                residual = merged["y_real"].to_numpy() - merged["yhat"].to_numpy()
                ds = merged["ds"]

                ax.axhline(0, color="black", linewidth=0.8, zorder=2)

                if np.allclose(residual, 0, atol=1e-6):
                    ax.text(
                        0.5,
                        0.5,
                        "yhat = y_real in-sample\n(sin residuales)",
                        transform=ax.transAxes,
                        ha="center",
                        va="center",
                        fontsize=10,
                        color="#999999",
                        style="italic",
                    )
                else:
                    ax.plot(ds, residual, color=style.color, linewidth=0.8, alpha=0.9, zorder=3)

                    pos = np.where(residual >= 0, residual, 0)
                    neg = np.where(residual < 0, residual, 0)
                    ax.fill_between(ds, 0, pos, color=style.color, alpha=0.3, zorder=1)
                    ax.fill_between(ds, 0, neg, color=style.color, alpha=0.15, zorder=1)

                _add_covid_band(ax, compact=True)

        ax.set_title(style.label, fontweight="bold", fontsize=11)
        ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=cc.ALPHA_GRID)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        if r == 1:
            ax.set_xlabel("Fecha", fontsize=10)
        if c == 0:
            ax.set_ylabel("Residual (Real - Predicho)", fontsize=10)

    _suptitle(fig, "Residuales por Modelo", pad, ent, modo)
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig
