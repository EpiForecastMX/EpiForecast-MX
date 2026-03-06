# src/epiforecast/visualization/comparison_builders.py
"""Pure rendering functions for model comparison charts.

Each builder receives DataFrames + config and returns a matplotlib Figure.
No I/O (no file loading, no saving).
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.constants import (
    COVID_BADGE_EC,
    COVID_BADGE_FC,
    COVID_END,
    COVID_SPAN_COLOR,
    COVID_START,
    COVID_TEXT_COLOR,
    RATE_PER,
)
from epiforecast.utils.config import conf
from epiforecast.visualization import chart_constants as cc
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    COLOR_REAL_OVERLAY,
    MODEL_STYLES,
)

_TZ_CDMX = ZoneInfo("America/Mexico_City")
_COVID_START = pd.Timestamp(COVID_START)
_COVID_END = pd.Timestamp(COVID_END)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_covid_band(ax: Axes, *, compact: bool = False) -> None:
    """Add a shaded COVID-19 band with optional badge label."""
    ax.axvspan(
        _COVID_START,
        _COVID_END,
        alpha=cc.ALPHA_COVID,
        color=COVID_SPAN_COLOR,
        zorder=0,
    )
    mid_covid = _COVID_START + (_COVID_END - _COVID_START) / 2
    fs = 5.5 if compact else cc.FS_COVID
    ax.annotate(
        "COVID-19",
        xy=(mid_covid, 1.0),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        fontweight="bold",
        color=COVID_TEXT_COLOR,
        ha="center",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.2",
            fc=COVID_BADGE_FC,
            ec=COVID_BADGE_EC,
            alpha=0.85,
            lw=0.5,
        ),
    )


def _add_cutoff_line(ax: Axes, cutoff: pd.Timestamp, *, compact: bool = False) -> None:
    """Add dashed cutoff line with labels."""
    ax.axvline(
        cutoff,
        color=COLOR_CUTOFF,
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        zorder=7,
    )
    if not compact:
        return
    fs = 6
    ax.annotate(
        "Hist.",
        xy=(cutoff, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        color="#555555",
        ha="right",
        va="top",
    )
    ax.annotate(
        "Pron.",
        xy=(cutoff, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        color=COLOR_CUTOFF,
        ha="left",
        va="top",
    )


def _add_cv_zone(ax: Axes, cutoff: pd.Timestamp, *, compact: bool = False) -> None:
    """Add shaded train/test CV zone."""
    fecha_corte = pd.Timestamp(conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"))
    ax.axvspan(
        fecha_corte,
        cutoff,
        alpha=0.06,
        color="#888888",
        zorder=0,
    )
    ax.axvline(
        fecha_corte,
        color="#888888",
        ls=":",
        lw=0.8,
        alpha=0.6,
        zorder=6,
    )
    if compact:
        fs = 5.5
        ax.annotate(
            "Entren.",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=fs,
            color="#888888",
            ha="right",
            va="top",
        )
        ax.annotate(
            "Prueba CV",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=fs,
            color="#888888",
            ha="left",
            va="top",
        )


def _add_forecast_band(ax: Axes, grp: pd.DataFrame, cutoff: pd.Timestamp, color: str) -> None:
    """Add 80% confidence band in the forecast zone."""
    if "yhat_lower" not in grp.columns or "yhat_upper" not in grp.columns:
        return
    future = grp[grp["ds"] > cutoff]
    if future.empty:
        return
    ax.fill_between(
        future["ds"],
        future["yhat_lower"],
        future["yhat_upper"],
        alpha=0.15,
        color=color,
        zorder=1,
    )


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


def _suptitle(fig: Figure, chart_type: str, pad: str, ent: str, modo: str) -> None:
    """Set a consistent suptitle."""
    ent_display = ent if ent else "Nacional"
    fig.suptitle(
        f"{chart_type}: {pad} - {ent_display} ({modo})",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )


def _merge_real_pred(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    pred: pd.DataFrame,
) -> pd.DataFrame:
    """Merge real and predicted values on date, returning aligned rows."""
    real = pd.DataFrame({"ds": serie_real["ds"], "y_real": target_y.values})
    merged = real.merge(pred[["ds", "yhat"]], on="ds", how="inner")
    return merged.dropna(subset=["y_real", "yhat"])


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
