# src/epiforecast/visualization/avance5_charts.py
"""Pure rendering functions for Avance 5 charts.

Each builder receives DataFrames and returns a matplotlib Figure.  No I/O.
Las primitivas de panel viven en ``avance5_panels`` y los graficos de metricas en
``avance5_metric_charts`` (re-exportados aqui por compatibilidad).
"""

from __future__ import annotations

from typing import Any

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats

from epiforecast.constants import VIZ_DPI_PRINT
from epiforecast.visualization.avance5_metric_charts import (
    build_error_boxplots,
    build_feature_importance,
    build_metric_bars,
    build_win_rate_heatmap,
)
from epiforecast.visualization.avance5_panels import (
    _clean_spines,
    _covid_band,
    _cutoff_line,
    _stamp,
)
from epiforecast.visualization.comparison_config import (
    COLOR_REAL_OVERLAY,
    MODEL_STYLES,
)

# Re-export for the orchestrator
DPI = VIZ_DPI_PRINT

__all__ = [
    "DPI",
    "build_error_boxplots",
    "build_feature_importance",
    "build_metric_bars",
    "build_residual_analysis",
    "build_trend_prediction",
    "build_win_rate_heatmap",
]

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
