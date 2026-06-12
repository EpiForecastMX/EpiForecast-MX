# src/epiforecast/visualization/avance5_metric_charts.py
"""Builders de graficos de metricas/comparacion del Avance 5 (importancia, barras,
boxplots, heatmap de win-rate). Sin I/O."""

from __future__ import annotations

from typing import Any, cast

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.visualization.avance5_panels import (
    _clean_spines,
    _stamp,
)
from epiforecast.visualization.comparison_config import (
    MODEL_STYLES,
)

# ---------------------------------------------------------------------------
# Chart 3: Feature importance (2 paneles)
# ---------------------------------------------------------------------------


def build_feature_importance(
    importances_xgb: npt.NDArray[Any],
    feature_names_xgb: list[str],
    weights_stacking: npt.NDArray[Any],
    expert_names: list[str],
) -> Figure:
    """2 paneles: barras XGBoost (izq) + pesos expertos Stacking (der)."""
    fig, (ax_xgb, ax_stack) = plt.subplots(1, 2, figsize=(16, 8))

    # Panel izquierdo: XGBoost feature importance
    ensemble_color = MODEL_STYLES["ensemble"].color
    idx_sorted = np.argsort(importances_xgb)
    sorted_names = [feature_names_xgb[i] for i in idx_sorted]
    sorted_vals = importances_xgb[idx_sorted]

    ax_xgb.barh(range(len(sorted_names)), sorted_vals, color=ensemble_color, alpha=0.85)
    ax_xgb.set_yticks(range(len(sorted_names)))
    ax_xgb.set_yticklabels(sorted_names, fontsize=9)
    ax_xgb.set_xlabel("Importancia (gain)", fontsize=11)
    ax_xgb.set_title("XGBoost: importancia de features", fontweight="bold", fontsize=12)
    _clean_spines(ax_xgb)

    # Panel derecho: Pesos expertos Stacking
    stacking_color = MODEL_STYLES["stacking"].color
    expert_colors = [stacking_color, "#4A148C", "#00695C"]
    bars = ax_stack.bar(
        range(len(expert_names)),
        weights_stacking,
        color=expert_colors[: len(expert_names)],
        alpha=0.85,
        edgecolor="white",
        linewidth=1.5,
    )
    ax_stack.set_xticks(range(len(expert_names)))
    ax_stack.set_xticklabels(expert_names, fontsize=11)
    ax_stack.set_ylabel("Peso normalizado", fontsize=11)
    ax_stack.set_title("Stacking: pesos de expertos", fontweight="bold", fontsize=12)
    ax_stack.set_ylim(0, 1.0)
    for bar, w in zip(bars, weights_stacking, strict=False):
        ax_stack.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{w:.3f}",
            ha="center",
            fontsize=11,
            fontweight="bold",
        )
    _clean_spines(ax_stack)

    fig.suptitle(
        "Importancia de features y pesos de expertos",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig


# ---------------------------------------------------------------------------
# Chart 4: Barras de metricas agrupadas
# ---------------------------------------------------------------------------


def build_metric_bars(
    merged: pd.DataFrame,
    model_keys: list[str],
    padecimiento: str | None = None,
) -> Figure:
    """Grid 2x2: una metrica por panel (escala Y independiente) + tabla resumen."""
    data = merged.copy()
    if padecimiento:
        data = data[data["padecimiento"] == padecimiento]

    metric_names = ["RMSE", "MAE", "SMAPE (%)", "MASE (vs naive)"]
    metric_keys = ["rmse", "mae", "smape", "mase"]
    grid_pos = [(0, 0), (0, 1), (1, 0), (1, 1)]

    # Recopilar valores por modelo
    rows: list[dict[str, object]] = []
    for mk in model_keys:
        style = MODEL_STYLES.get(mk)
        if style is None:
            continue
        vals: list[float] = []
        for metric in metric_keys:
            col = f"{metric}_{mk}"
            v = data[col].mean(skipna=True) if col in data.columns else float("nan")
            vals.append(v)
        rows.append({"model": style.label, "color": style.color, "values": vals})

    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(3, 2, height_ratios=[5, 5, 2], hspace=0.35, wspace=0.3)

    # 2x2 grid de barras horizontales
    for m_idx, (metric_label, (r, c)) in enumerate(zip(metric_names, grid_pos, strict=True)):
        ax = fig.add_subplot(gs[r, c])
        model_labels = [str(row["model"]) for row in rows]
        values = [cast(list[float], row["values"])[m_idx] for row in rows]
        colors = [str(row["color"]) for row in rows]

        best_idx = int(np.nanargmin(values)) if values else -1
        y_pos = np.arange(len(rows))

        for i, (val, color) in enumerate(zip(values, colors, strict=True)):
            edgecolor = "black" if i == best_idx else "white"
            lw = 2.0 if i == best_idx else 0.8
            ax.barh(
                i,
                val,
                color=color,
                alpha=0.85,
                edgecolor=edgecolor,
                linewidth=lw,
            )
            # Anotacion al final de la barra
            star = " *" if i == best_idx else ""
            offset = ax.get_xlim()[1] * 0.01 if ax.get_xlim()[1] > 0 else 0.01
            ax.text(
                val + offset,
                i,
                f"{val:.2f}{star}",
                va="center",
                fontsize=9,
                fontweight="bold",
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(model_labels, fontsize=10)
        ax.set_title(metric_label, fontweight="bold", fontsize=12)
        ax.invert_yaxis()
        # Extender xlim para que quepan las anotaciones
        xmax = max(values) if values else 1
        ax.set_xlim(0, xmax * 1.25)
        _clean_spines(ax)

    # Suptitle
    title_suffix = f": {padecimiento}" if padecimiento else " (global)"
    fig.suptitle(
        f"Comparación de métricas{title_suffix}",
        fontweight="bold",
        fontsize=14,
        y=0.98,
    )

    # Tabla resumen en el area inferior (spanning 2 columnas)
    ax_tbl = fig.add_subplot(gs[2, :])
    ax_tbl.axis("off")

    col_labels = ["RMSE", "MAE", "SMAPE", "MASE"]
    cell_text = []
    row_labels = []
    row_colors = []
    for row in rows:
        row_labels.append(str(row["model"]))
        row_colors.append(str(row["color"]))
        cell_text.append([f"{v:.2f}" for v in cast(list[float], row["values"])])

    if cell_text:
        table = ax_tbl.table(
            cellText=cell_text,
            rowLabels=row_labels,
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.4)
        for i, color in enumerate(row_colors):
            table[i + 1, -1].set_facecolor(color)
            table[i + 1, -1].set_text_props(color="white", fontweight="bold")
    _stamp(fig)
    return fig


# ---------------------------------------------------------------------------
# Chart 5: Boxplots de errores
# ---------------------------------------------------------------------------


def build_error_boxplots(
    merged: pd.DataFrame,
    model_keys: list[str],
    padecimiento: str | None = None,
) -> Figure:
    """Boxplots de RMSE por modelo (mediana, IQR, outliers)."""
    data = merged.copy()
    if padecimiento:
        data = data[data["padecimiento"] == padecimiento]

    fig, ax = plt.subplots(figsize=(10, 7))

    box_data: list[npt.NDArray[Any]] = []
    labels: list[str] = []
    colors: list[str] = []
    for mk in model_keys:
        col = f"rmse_{mk}"
        if col not in data.columns:
            continue
        vals = data[col].dropna().to_numpy()
        if len(vals) == 0:
            continue
        box_data.append(vals)
        style = MODEL_STYLES.get(mk)
        labels.append(style.label if style else mk)
        colors.append(style.color if style else "#333333")

    if box_data:
        bp = ax.boxplot(
            box_data,
            tick_labels=labels,
            patch_artist=True,
            showfliers=True,
            flierprops={"markersize": 3, "alpha": 0.5},
        )
        for patch, color in zip(bp["boxes"], colors, strict=False):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        for median in bp["medians"]:
            median.set_color("black")
            median.set_linewidth(2)

    title_suffix = f": {padecimiento}" if padecimiento else " (global)"
    ax.set_title(
        f"Distribución de errores RMSE{title_suffix}",
        fontweight="bold",
        fontsize=13,
    )
    ax.set_ylabel("RMSE", fontsize=11)
    _clean_spines(ax)
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return fig


# ---------------------------------------------------------------------------
# Chart 6: Heatmap de win rate por estado
# ---------------------------------------------------------------------------


def build_win_rate_heatmap(
    win_df: pd.DataFrame,
    padecimiento: str,
    model_keys: list[str],
) -> Figure:
    """Heatmap: 32 estados x 4 modelos con porcentaje de victorias."""
    model_labels = [MODEL_STYLES[mk].label for mk in model_keys if mk in MODEL_STYLES]
    cols_present = [c for c in model_labels if c in win_df.columns]
    if not cols_present:
        fig, ax = plt.subplots(figsize=(8, 10))
        ax.text(0.5, 0.5, "Sin datos", transform=ax.transAxes, ha="center")
        return fig

    matrix = win_df.set_index("Entidad")[cols_present].values
    entidades = win_df["Entidad"].tolist()

    fig, ax = plt.subplots(figsize=(10, max(12, len(entidades) * 0.4)))

    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)

    ax.set_xticks(range(len(cols_present)))
    ax.set_xticklabels(cols_present, fontsize=11, fontweight="bold")
    ax.set_yticks(range(len(entidades)))
    ax.set_yticklabels(entidades, fontsize=8)

    # Anotaciones
    for i in range(len(entidades)):
        for j in range(len(cols_present)):
            val = matrix[i, j]
            text_color = "white" if val > 60 else "black"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center", fontsize=7, color=text_color)

    fig.colorbar(im, ax=ax, label="Porcentaje de victorias (%)", shrink=0.6)

    ax.set_title(
        f"Win rate por entidad: {padecimiento}",
        fontweight="bold",
        fontsize=13,
        pad=12,
    )
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return fig
