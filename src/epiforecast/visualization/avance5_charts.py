"""Pure rendering functions for Avance 5 charts.

Each builder receives DataFrames and returns a matplotlib Figure.  No I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats

from epiforecast.constants import COVID_END, COVID_START, VIZ_DPI_PRINT
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    COLOR_REAL_OVERLAY,
    COVID_FILL,
    MODEL_STYLES,
)

_TZ_CDMX = ZoneInfo("America/Mexico_City")
_COVID_START = pd.Timestamp(COVID_START)
_COVID_END = pd.Timestamp(COVID_END)

# Re-export for the orchestrator
DPI = VIZ_DPI_PRINT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _covid_band(ax: Axes) -> None:
    ax.axvspan(
        _COVID_START.to_pydatetime(),
        _COVID_END.to_pydatetime(),
        color=COVID_FILL,
        alpha=0.5,
        zorder=0,
    )


def _cutoff_line(ax: Axes, cutoff: pd.Timestamp) -> None:
    ax.axvline(
        cutoff.to_pydatetime(),
        color=COLOR_CUTOFF,
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        zorder=7,
    )


def _clean_spines(ax: Axes) -> None:
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)


def _stamp(fig: Figure) -> None:
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
# Chart 1: Tendencia + prediccion
# ---------------------------------------------------------------------------


def build_trend_prediction(
    serie_real: pd.DataFrame,
    forecast_winner: pd.DataFrame,
    forecast_prophet: pd.DataFrame,
    padecimiento: str,
    modelo_ganador: str,
    cutoff: pd.Timestamp,
) -> Figure:
    """Serie real + modelo ganador + Prophet base + bandas de incertidumbre."""
    fig, ax = plt.subplots(figsize=(14, 6))

    # Real
    ax.plot(
        serie_real["ds"],
        serie_real["y"],
        color=COLOR_REAL_OVERLAY,
        linewidth=2,
        label="Historial real",
        zorder=1,
    )

    ganador_style = MODEL_STYLES.get(modelo_ganador, MODEL_STYLES["stacking"])

    # Modelo ganador
    ax.plot(
        forecast_winner["ds"],
        forecast_winner["yhat"],
        color=ganador_style.color,
        linewidth=2,
        label=ganador_style.label,
        zorder=4,
    )
    if "yhat_lower" in forecast_winner.columns and "yhat_upper" in forecast_winner.columns:
        ax.fill_between(
            forecast_winner["ds"],
            forecast_winner["yhat_lower"],
            forecast_winner["yhat_upper"],
            color=ganador_style.color,
            alpha=0.15,
            zorder=2,
        )

    # Prophet base
    prophet_style = MODEL_STYLES["prophet"]
    ax.plot(
        forecast_prophet["ds"],
        forecast_prophet["yhat"],
        color=prophet_style.color,
        linewidth=1.2,
        linestyle="--",
        alpha=0.7,
        label="Prophet (base)",
        zorder=3,
    )

    _covid_band(ax)
    _cutoff_line(ax, cutoff)

    ax.set_title(
        f"Tendencia y predicción: {padecimiento} (modelo: {ganador_style.label})",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Casos semanales", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    _clean_spines(ax)
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return fig


# ---------------------------------------------------------------------------
# Chart 2: Analisis de residuales (2x2)
# ---------------------------------------------------------------------------


def build_residual_analysis(
    residuals: npt.NDArray[Any],
    dates: pd.Series,
    model_name: str,
    color: str,
    padecimiento: str,
) -> Figure:
    """2x2: residuales vs tiempo, histograma+normal, QQ-plot, ACF."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # (a) Residuales vs tiempo
    ax = axes[0, 0]
    ax.plot(dates, residuals, color=color, linewidth=0.8, alpha=0.9)
    ax.axhline(0, color="black", linewidth=0.8)
    pos = np.where(residuals >= 0, residuals, 0)
    neg = np.where(residuals < 0, residuals, 0)
    ax.fill_between(dates, 0, pos, color=color, alpha=0.2)
    ax.fill_between(dates, 0, neg, color=color, alpha=0.1)
    _covid_band(ax)
    ax.set_title("(a) Residuales vs tiempo", fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Residual")
    _clean_spines(ax)

    # (b) Histograma + curva normal
    ax = axes[0, 1]
    ax.hist(residuals, bins=30, density=True, color=color, alpha=0.6, edgecolor="white")
    mu, sigma = float(np.mean(residuals)), float(np.std(residuals))
    if sigma > 0:
        x_norm = np.linspace(mu - 4 * sigma, mu + 4 * sigma, 200)
        ax.plot(x_norm, stats.norm.pdf(x_norm, mu, sigma), "k-", linewidth=1.5)
    ax.set_title("(b) Histograma + normal", fontweight="bold")
    ax.set_xlabel("Residual")
    ax.set_ylabel("Densidad")
    _clean_spines(ax)

    # (c) QQ-plot
    ax = axes[1, 0]
    stats.probplot(residuals, dist="norm", plot=ax)
    ax.get_lines()[0].set_markerfacecolor(color)
    ax.get_lines()[0].set_markeredgecolor(color)
    ax.get_lines()[0].set_markersize(3)
    ax.set_title("(c) QQ-plot", fontweight="bold")
    _clean_spines(ax)

    # (d) ACF
    ax = axes[1, 1]
    _plot_acf_manual(residuals, ax, color, n_lags=40)
    ax.set_title("(d) Autocorrelación (ACF)", fontweight="bold")
    ax.set_xlabel("Lag")
    ax.set_ylabel("ACF")
    _clean_spines(ax)

    fig.suptitle(
        f"Análisis de residuales: {padecimiento} ({model_name})",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )
    _stamp(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig


def _plot_acf_manual(residuals: npt.NDArray[Any], ax: Axes, color: str, n_lags: int = 40) -> None:
    """Plot ACF without statsmodels dependency (manual implementation)."""
    n = len(residuals)
    mean = np.mean(residuals)
    var = np.var(residuals)
    if var == 0 or n < n_lags + 1:
        ax.text(0.5, 0.5, "Datos insuficientes", transform=ax.transAxes, ha="center")
        return
    acf_vals = []
    for lag in range(n_lags + 1):
        cov = np.sum((residuals[: n - lag] - mean) * (residuals[lag:] - mean)) / n
        acf_vals.append(cov / var)
    lags = np.arange(n_lags + 1)
    ax.bar(lags, acf_vals, width=0.4, color=color, alpha=0.7)
    # Bandas de confianza (95%)
    conf = 1.96 / np.sqrt(n)
    ax.axhline(conf, color="gray", linestyle="--", linewidth=0.8)
    ax.axhline(-conf, color="gray", linestyle="--", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.5)


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
