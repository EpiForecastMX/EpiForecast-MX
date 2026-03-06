"""Forecast chart renderer: publication-quality Prophet forecast visualizations."""

import os
from typing import Any

from matplotlib.axes import Axes
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.visualization import chart_constants as cc
from epiforecast.visualization.chart_annotations import (
    _anotar_divisores,
    _anotar_zona_cv,
    _render_ficha_tecnica,
)
from epiforecast.visualization.chart_renderer import plot_series as _plot_series


def graficar_pronostico(
    forecast: pd.DataFrame,
    serie: pd.DataFrame,
    titulo: str,
    padecimiento: str,
    nombre_archivo: str,
    carpeta_salida: str,
    conf_paleta: dict[str, Any],
    conf_paleta_padecimiento: dict[str, Any],
    conf_covid: dict[str, Any],
    metricas: dict[str, Any] | None = None,
) -> str:
    """Gráfico de pronóstico estilo publicación IMSS con observaciones reales,
    banda de intervalo, franja COVID-19, outliers IQR y ficha técnica.

    Args:
        forecast:               DataFrame Prophet con ds, yhat, yhat_lower, yhat_upper.
        serie:                  DataFrame con columnas ds (datetime) e y (observaciones).
        titulo:                 Título del gráfico (formato: "Padecimiento · Nivel · Modo").
        padecimiento:           Nombre normalizado (Depresion / Parkinson / Alzheimer).
        nombre_archivo:         Nombre del PNG sin extensión.
        carpeta_salida:         Directorio de salida para el PNG.
        conf_paleta:            Dict de colores IMSS_COLORS.
        conf_paleta_padecimiento: Dict de paleta por padecimiento PALETTE_PADECIMIENTO.
        conf_covid:             Dict con claves inicio/fin del periodo COVID-19.
        metricas:               Dict con mase, rmse, confianza del modelo (opcional).
    """
    forecast = forecast.dropna(subset=["ds", "yhat", "yhat_lower", "yhat_upper"]).copy()
    serie = serie.dropna(subset=["ds", "y"]).copy()

    outliers, fecha_max_datos = _prepare_data(serie)
    fecha_max_fc = forecast["ds"].max()
    colors = _build_palette(padecimiento, conf_paleta, conf_paleta_padecimiento)
    title_parts = _parse_title(titulo, padecimiento, serie, fecha_max_fc)

    fig, ax = _setup_figure(title_parts, colors)
    _plot_series(ax, forecast, serie, outliers, fecha_max_datos, fecha_max_fc, colors, conf_covid)
    _anotar_divisores(ax, fecha_max_datos, colors["div"], colors["fc"])
    _anotar_zona_cv(ax, fecha_max_datos, colors["gray"])
    _format_axes(ax, colors)
    _add_legend_and_ficha(fig, ax, metricas)

    ruta = os.path.join(carpeta_salida, f"{nombre_archivo}.png")
    fig.savefig(ruta, dpi=VIZ_DPI_SCREEN, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return ruta


# ── Private helpers ──────────────────────────────────────────────────


def _prepare_data(serie: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Calcula outliers IQR y fecha máxima de la serie observada."""
    y = serie["y"]
    q1, q3 = y.quantile(0.25), y.quantile(0.75)
    iqr = q3 - q1
    out_mask = (y < q1 - 1.5 * iqr) | (y > q3 + 1.5 * iqr)
    return serie[out_mask], serie["ds"].max()


def _build_palette(
    padecimiento: str, conf_paleta: dict[str, Any], conf_pad: dict[str, Any]
) -> dict[str, str]:
    """Construye diccionario de colores usando la paleta IMSS por padecimiento."""
    pad_colors = conf_pad.get(padecimiento, {"c1": "#E74C3C", "cl": "#F5B7B1"})
    return {
        "obs": "#1B2A4A",
        "fc": pad_colors["c1"],
        "band": pad_colors["cl"],
        "outlier": "#D84315",
        "div": "#555555",
        "gray": conf_paleta["cool_gray"],
        "text": conf_paleta["neutral_black"],
    }


def _parse_title(
    titulo: str, padecimiento: str, serie: pd.DataFrame, fecha_max_fc: pd.Timestamp
) -> dict[str, Any]:
    """Parsea el título compuesto en componentes para suptitle y subtitle."""
    parts = titulo.split(" · ")
    return {
        "pad_display": (parts[0] if parts else padecimiento).replace("Depresion", "Depresión"),
        "nivel": parts[1] if len(parts) > 1 else "",
        "modo": (parts[2] if len(parts) > 2 else "").capitalize(),
        "anio_ini": serie["ds"].min().year,
        "anio_fin": fecha_max_fc.year,
    }


def _setup_figure(title_parts: dict[str, Any], colors: dict[str, str]) -> tuple[Figure, Axes]:
    """Crea la figura con títulos y márgenes IMSS."""
    fig, ax = plt.subplots(figsize=cc.FIGSIZE)
    fig.subplots_adjust(**cc.MARGINS)
    fig.suptitle(
        f"{title_parts['pad_display']} — Pronóstico Semanal",
        fontsize=cc.FS_SUPTITLE,
        fontweight="bold",
        color=colors["text"],
        y=cc.SUPTITLE_Y,
    )
    ax.set_title(
        f"{title_parts['nivel']}  ·  {title_parts['modo']}  ·  "
        f"{title_parts['anio_ini']}–{title_parts['anio_fin']}",
        fontsize=cc.FS_SUBTITLE,
        color=colors["gray"],
        pad=10,
    )
    return fig, ax


def _format_axes(ax: Axes, colors: dict[str, str]) -> None:
    """Aplica formato de ejes estilo IMSS."""
    ax.set_xlabel("")
    ax.set_ylabel("Incrementos semanales", fontsize=cc.FS_LABEL, color=colors["text"])
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=cc.ALPHA_GRID, color=colors["gray"], linestyle="-", linewidth=0.5)
    ax.xaxis.grid(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())  # type: ignore[no-untyped-call]
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))  # type: ignore[no-untyped-call]
    ax.tick_params(axis="both", labelsize=cc.FS_TICK, colors=colors["text"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(colors["gray"])
        ax.spines[spine].set_linewidth(cc.LW_SPINE)


def _add_legend_and_ficha(fig: Figure, ax: Axes, metricas: dict[str, Any] | None) -> None:
    """Agrega leyenda compacta y ficha técnica al pie del gráfico."""
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=cc.LEGEND_ANCHOR,
        ncol=len(handles),
        fontsize=cc.FS_LEGEND,
        frameon=True,
        facecolor="white",
        edgecolor="#cccccc",
        framealpha=0.9,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=2.0,
    )
    if metricas:
        _render_ficha_tecnica(fig, metricas)
