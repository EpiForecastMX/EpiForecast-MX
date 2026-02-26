"""Forecast chart renderer: publication-quality Prophet forecast visualizations."""

import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.visualization.chart_annotations import (
    _anotar_divisores,
    _anotar_zona_cv,
    _render_ficha_tecnica,
)


def graficar_pronostico(
    forecast: pd.DataFrame,
    serie: pd.DataFrame,
    titulo: str,
    padecimiento: str,
    nombre_archivo: str,
    carpeta_salida: str,
    conf_paleta: dict,
    conf_paleta_padecimiento: dict,
    conf_covid: dict,
    metricas: dict | None = None,
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
    fig.savefig(ruta, dpi=VIZ_DPI_SCREEN, facecolor="white", edgecolor="none")
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


def _build_palette(padecimiento: str, conf_paleta: dict, conf_pad: dict) -> dict:
    """Construye diccionario de colores a partir de la paleta IMSS."""
    pal = conf_pad.get(padecimiento, {"c1": conf_paleta["burgundy"], "cl": "#D4758B"})
    return {
        "obs": conf_paleta["teal"],
        "fc": pal["c1"],
        "band": pal["cl"],
        "outlier": "#D84315",
        "div": "#555555",
        "gray": conf_paleta["cool_gray"],
        "text": conf_paleta["neutral_black"],
    }


def _parse_title(
    titulo: str, padecimiento: str, serie: pd.DataFrame, fecha_max_fc: pd.Timestamp
) -> dict:
    """Parsea el título compuesto en componentes para suptitle y subtitle."""
    parts = titulo.split(" · ")
    return {
        "pad_display": (parts[0] if parts else padecimiento).replace("Depresion", "Depresión"),
        "nivel": parts[1] if len(parts) > 1 else "",
        "modo": (parts[2] if len(parts) > 2 else "").capitalize(),
        "anio_ini": serie["ds"].min().year,
        "anio_fin": fecha_max_fc.year,
    }


def _setup_figure(title_parts: dict, colors: dict) -> tuple[plt.Figure, plt.Axes]:
    """Crea la figura con títulos y márgenes IMSS."""
    fig, ax = plt.subplots(figsize=(18, 7.5))
    fig.subplots_adjust(bottom=0.13, top=0.89, left=0.055, right=0.975)
    fig.suptitle(
        f"{title_parts['pad_display']} — Pronóstico Semanal",
        fontsize=16, fontweight="bold", color=colors["text"], y=0.96,
    )
    ax.set_title(
        f"{title_parts['nivel']}  ·  {title_parts['modo']}  ·  "
        f"{title_parts['anio_ini']}–{title_parts['anio_fin']}",
        fontsize=11, color=colors["gray"], pad=10,
    )
    return fig, ax


def _plot_series(
    ax: plt.Axes,
    forecast: pd.DataFrame,
    serie: pd.DataFrame,
    outliers: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    fecha_max_fc: pd.Timestamp,
    colors: dict,
    conf_covid: dict,
) -> None:
    """Dibuja todas las capas de datos: zona pronóstico, COVID, banda, observaciones, línea, outliers."""
    # Zona pronóstico
    ax.axvspan(fecha_max_datos, fecha_max_fc, alpha=0.04, color=colors["fc"], zorder=0)

    # COVID-19
    covid_ini = pd.Timestamp(conf_covid["inicio"])
    covid_fin = pd.Timestamp(conf_covid["fin"])
    ax.axvspan(covid_ini, covid_fin, alpha=0.07, color="#E53935", zorder=0)  # type: ignore[arg-type]
    mid_covid = covid_ini + (covid_fin - covid_ini) / 2
    ax.annotate(
        "COVID-19", xy=(mid_covid, 1.0), xycoords=("data", "axes fraction"),  # type: ignore[arg-type]
        fontsize=7, fontweight="bold", color="#C62828", ha="center", va="top",
        bbox=dict(boxstyle="round,pad=0.25", fc="#FFEBEE", ec="#EF9A9A", alpha=0.85, lw=0.6),
    )

    # Banda de predicción
    ax.fill_between(
        forecast["ds"], forecast["yhat_lower"], forecast["yhat_upper"],
        alpha=0.20, color=colors["band"], zorder=1, label="Intervalo 80 %",
    )

    # Observaciones reales
    ax.scatter(
        serie["ds"], serie["y"], s=15, color=colors["obs"],
        alpha=0.45, zorder=3, label="Observaciones reales",
    )

    # Línea de pronóstico
    ax.plot(
        forecast["ds"], forecast["yhat"], color=colors["fc"],
        linewidth=2.2, zorder=4, label="Pronóstico Prophet",
    )

    # Outliers
    if len(outliers) > 0:
        ax.scatter(
            outliers["ds"], outliers["y"], marker="^", s=45,
            color=colors["outlier"], edgecolors="white", linewidths=0.8,
            zorder=5, label=f"Outliers IQR (n = {len(outliers)})",
        )


def _format_axes(ax: plt.Axes, colors: dict) -> None:
    """Aplica formato de ejes estilo IMSS."""
    ax.set_xlabel("")
    ax.set_ylabel("Incrementos semanales", fontsize=11, color=colors["text"])
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=0.25, color=colors["gray"], linestyle="-", linewidth=0.5)
    ax.xaxis.grid(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="both", labelsize=10, colors=colors["text"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(colors["gray"])
        ax.spines[spine].set_linewidth(0.5)


def _add_legend_and_ficha(fig: plt.Figure, ax: plt.Axes, metricas: dict | None) -> None:
    """Agrega leyenda compacta y ficha técnica al pie del gráfico."""
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", bbox_to_anchor=(0.515, 0.04),
        ncol=len(handles), fontsize=9.5, frameon=False,
        handlelength=1.8, handletextpad=0.4, columnspacing=2.0,
    )
    if metricas:
        _render_ficha_tecnica(fig, metricas)
