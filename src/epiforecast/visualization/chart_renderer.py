"""Low-level rendering for forecast charts: series, bands, COVID zone, outliers.

Extracted from forecast_chart.py for SRP compliance (max 300 lines per module).
"""

from typing import Any

from matplotlib.axes import Axes
import pandas as pd

from epiforecast.constants import (
    COVID_BADGE_EC,
    COVID_BADGE_FC,
    COVID_SPAN_COLOR,
    COVID_TEXT_COLOR,
)
from epiforecast.visualization import chart_constants as cc


def plot_series(
    ax: Axes,
    forecast: pd.DataFrame,
    serie: pd.DataFrame,
    outliers: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    fecha_max_fc: pd.Timestamp,
    colors: dict[str, Any],
    conf_covid: dict[str, Any],
) -> None:
    """Dibuja todas las capas: zona pronostico, COVID, banda, observaciones, outliers."""
    ax.axvspan(
        fecha_max_datos,
        fecha_max_fc,
        alpha=cc.ALPHA_FORECAST_ZONE,
        color=colors["fc"],
        zorder=0,
    )

    # COVID-19
    covid_ini = pd.Timestamp(conf_covid["inicio"])
    covid_fin = pd.Timestamp(conf_covid["fin"])
    ax.axvspan(
        covid_ini,
        covid_fin,
        alpha=cc.ALPHA_COVID,
        color=COVID_SPAN_COLOR,
        zorder=0,
    )
    mid_covid = covid_ini + (covid_fin - covid_ini) / 2
    ax.annotate(
        "COVID-19",
        xy=(mid_covid, 1.0),
        xycoords=("data", "axes fraction"),
        fontsize=cc.FS_COVID,
        fontweight="bold",
        color=COVID_TEXT_COLOR,
        ha="center",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.25", fc=COVID_BADGE_FC, ec=COVID_BADGE_EC, alpha=0.85, lw=0.6
        ),
    )

    fc_overlap = forecast[forecast["ds"] <= fecha_max_datos]
    fc_future = forecast[forecast["ds"] > fecha_max_datos]

    if not fc_future.empty:
        ax.fill_between(
            fc_future["ds"],
            fc_future["yhat_lower"],
            fc_future["yhat_upper"],
            alpha=0.15,
            color=colors["band"],
            zorder=1,
            label="Intervalo 80 %",
        )
        ax.plot(
            fc_future["ds"],
            fc_future["yhat_lower"],
            color=colors["band"],
            alpha=0.2,
            lw=0.5,
            zorder=1,
        )
        ax.plot(
            fc_future["ds"],
            fc_future["yhat_upper"],
            color=colors["band"],
            alpha=0.2,
            lw=0.5,
            zorder=1,
        )

    if not fc_overlap.empty:
        ax.plot(
            fc_overlap["ds"],
            fc_overlap["yhat"],
            color=colors["fc"],
            alpha=0.50,
            linewidth=1.2,
            linestyle="-",
            zorder=3,
            label="Ajuste del Modelo (Backtesting)",
        )

    if not fc_future.empty:
        ax.plot(
            fc_future["ds"],
            fc_future["yhat"],
            color=colors["fc"],
            alpha=0.85,
            linewidth=1.8,
            linestyle="-",
            zorder=3,
            label="Prediccion de Casos",
        )

    serie_sorted = serie.sort_values("ds")
    y_smooth = serie_sorted["y"].rolling(cc.ROLLING_OBS, min_periods=1, center=True).mean()
    ax.plot(
        serie_sorted["ds"],
        y_smooth,
        color=colors["obs"],
        alpha=1.0,
        linewidth=2.0,
        linestyle="-",
        zorder=5,
        label="Datos reales",
    )
    last_y = y_smooth.iloc[-1]
    ax.plot(
        fecha_max_datos,
        last_y,
        marker="o",
        markersize=8,
        color=colors["obs"],
        markeredgecolor="white",
        markeredgewidth=1.5,
        zorder=6,
    )

    if not fc_future.empty:
        idx_max = fc_future["yhat"].idxmax()
        pico_x = fc_future.loc[idx_max, "ds"]
        pico_y = fc_future.loc[idx_max, "yhat"]
        ax.annotate(
            f"Pico proyectado\n{pico_y:,.0f}",
            xy=(pico_x, pico_y),
            xytext=(0, 25),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold",
            color=colors["fc"],
            ha="center",
            arrowprops=dict(arrowstyle="->", color=colors["fc"], lw=1.2),
            zorder=7,
        )

    if len(outliers) > 0:
        ax.scatter(
            outliers["ds"],
            outliers["y"],
            marker="^",
            s=cc.SIZE_OUTLIER,
            color=colors["outlier"],
            edgecolors="white",
            linewidths=cc.LW_OUTLIER_EDGE,
            zorder=5,
            label=f"Outliers IQR (n = {len(outliers)})",
        )
