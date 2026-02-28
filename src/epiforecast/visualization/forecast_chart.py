"""Forecast chart renderer: publication-quality Prophet forecast visualizations."""

import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.utils.config import conf
from epiforecast.visualization.chart_annotations import (
    _anotar_divisores,
    _anotar_zona_cv,
    _render_ficha_tecnica,
)

# ── Layout constants ─────────────────────────────────────────────────
_FIGSIZE = (20, 8)
_MARGINS = {"bottom": 0.13, "top": 0.89, "left": 0.05, "right": 0.975}
_SUPTITLE_Y = 0.96
_LEGEND_ANCHOR = (0.515, 0.04)

# ── Font sizes ───────────────────────────────────────────────────────
_FS_SUPTITLE = 16
_FS_SUBTITLE = 11
_FS_LABEL = 11
_FS_LEGEND = 9.5
_FS_COVID = 6.5
_FS_TICK = 10

# ── Line / marker styling ───────────────────────────────────────────
_LW_FORECAST = 2.2
_LW_SPINE = 0.5
_LW_OUTLIER_EDGE = 1.0
_ALPHA_BAND = 0.20
_ALPHA_OBS = 0.45
_ALPHA_FORECAST_ZONE = 0.04
_ALPHA_COVID = 0.05
_ALPHA_GRID = 0.25
_SIZE_OBS = 15
_ROLLING_OBS = 4  # ventana de suavizado para observaciones (semanas)
_SIZE_OUTLIER = 70

# ── COVID badge colors ───────────────────────────────────────────────
_COVID_SPAN_COLOR = "#E53935"
_COVID_TEXT_COLOR = "#C62828"
_COVID_BADGE_FC = "#FFEBEE"
_COVID_BADGE_EC = "#EF9A9A"


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
    _plot_series(ax, forecast, serie, outliers, fecha_max_datos, fecha_max_fc, colors, conf_covid)  # type: ignore[arg-type]
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
    """Construye diccionario de colores: azul oscuro (historial) / rojo (pronostico)."""
    return {
        "obs": "#1B2A4A",
        "fc": "#E74C3C",
        "band": "#F5B7B1",
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
    fig, ax = plt.subplots(figsize=_FIGSIZE)
    fig.subplots_adjust(**_MARGINS)
    fig.suptitle(
        f"{title_parts['pad_display']} — Pronóstico Semanal",
        fontsize=_FS_SUPTITLE,
        fontweight="bold",
        color=colors["text"],
        y=_SUPTITLE_Y,
    )
    ax.set_title(
        f"{title_parts['nivel']}  ·  {title_parts['modo']}  ·  "
        f"{title_parts['anio_ini']}–{title_parts['anio_fin']}",
        fontsize=_FS_SUBTITLE,
        color=colors["gray"],
        pad=10,
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
    # Zona pronóstico (matplotlib acepta pd.Timestamp; type: ignore por stubs incompletos)
    ax.axvspan(
        fecha_max_datos,  # type: ignore[arg-type]
        fecha_max_fc,  # type: ignore[arg-type]
        alpha=_ALPHA_FORECAST_ZONE,
        color=colors["fc"],
        zorder=0,
    )

    # COVID-19
    covid_ini = pd.Timestamp(conf_covid["inicio"])
    covid_fin = pd.Timestamp(conf_covid["fin"])
    ax.axvspan(
        covid_ini,  # type: ignore[arg-type]  # matplotlib accepts Timestamp
        covid_fin,  # type: ignore[arg-type]
        alpha=_ALPHA_COVID,
        color=_COVID_SPAN_COLOR,
        zorder=0,
    )
    mid_covid = covid_ini + (covid_fin - covid_ini) / 2
    ax.annotate(
        "COVID-19",
        xy=(mid_covid, 1.0),  # type: ignore[arg-type]
        xycoords=("data", "axes fraction"),
        fontsize=_FS_COVID,
        fontweight="bold",
        color=_COVID_TEXT_COLOR,
        ha="center",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.25", fc=_COVID_BADGE_FC, ec=_COVID_BADGE_EC, alpha=0.85, lw=0.6
        ),
    )

    # ── Dividir pronostico en zona solapada vs zona futura ────────────
    fc_overlap = forecast[forecast["ds"] <= fecha_max_datos]
    fc_future = forecast[forecast["ds"] > fecha_max_datos]

    # Banda de confianza SOLO en zona futura
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
        # Bordes del intervalo
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

    # ── Pronostico zona solapada (sombra transparente detras de datos reales) ──
    if not fc_overlap.empty:
        ax.plot(
            fc_overlap["ds"],
            fc_overlap["yhat"],
            color=colors["fc"],
            alpha=0.35,
            linewidth=0.8,
            linestyle="-",
            zorder=3,
            label="Pronostico (solapado)",
        )

    # ── Pronostico zona futura (visible, es el forecast real) ──────────
    _model_display = {"prophet": "Prophet", "deepar": "DeepAR"}
    modelo_activo = _model_display.get(
        conf.get("modelo_activo", "prophet"), conf.get("modelo_activo", "prophet")
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
            label=f"Pronostico {modelo_activo}",
        )

    # ── Observaciones reales (linea DOMINANTE) ─────────────────────────
    serie_sorted = serie.sort_values("ds")
    y_smooth = serie_sorted["y"].rolling(_ROLLING_OBS, min_periods=1, center=True).mean()
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

    # ── Marcador de transicion (fin de datos reales) ───────────────────
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

    # ── Pico proyectado (solo en zona futura) ──────────────────────────
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

    # ── Outliers ───────────────────────────────────────────────────────
    if len(outliers) > 0:
        ax.scatter(
            outliers["ds"],
            outliers["y"],
            marker="^",
            s=_SIZE_OUTLIER,
            color=colors["outlier"],
            edgecolors="white",
            linewidths=_LW_OUTLIER_EDGE,
            zorder=5,
            label=f"Outliers IQR (n = {len(outliers)})",
        )


def _format_axes(ax: plt.Axes, colors: dict) -> None:
    """Aplica formato de ejes estilo IMSS."""
    ax.set_xlabel("")
    ax.set_ylabel("Incrementos semanales", fontsize=_FS_LABEL, color=colors["text"])
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=_ALPHA_GRID, color=colors["gray"], linestyle="-", linewidth=0.5)
    ax.xaxis.grid(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="both", labelsize=_FS_TICK, colors=colors["text"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(colors["gray"])
        ax.spines[spine].set_linewidth(_LW_SPINE)


def _add_legend_and_ficha(fig: plt.Figure, ax: plt.Axes, metricas: dict | None) -> None:
    """Agrega leyenda compacta y ficha técnica al pie del gráfico."""
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=_LEGEND_ANCHOR,
        ncol=len(handles),
        fontsize=_FS_LEGEND,
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
