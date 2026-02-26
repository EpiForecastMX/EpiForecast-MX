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
    # ── Preparación de datos ─────────────────────────────────────────
    forecast = forecast.dropna(subset=["ds", "yhat", "yhat_lower", "yhat_upper"]).copy()
    serie = serie.dropna(subset=["ds", "y"]).copy()
    y = serie["y"]
    Q1, Q3 = y.quantile(0.25), y.quantile(0.75)
    IQR = Q3 - Q1
    out_mask = (y < Q1 - 1.5 * IQR) | (y > Q3 + 1.5 * IQR)
    outliers = serie[out_mask]
    fecha_max_datos = serie["ds"].max()
    fecha_max_fc = forecast["ds"].max()

    # ── Paleta de colores ────────────────────────────────────────────
    pal = conf_paleta_padecimiento.get(
        padecimiento,
        {"c1": conf_paleta["burgundy"], "cl": "#D4758B"},
    )
    c_obs = conf_paleta["teal"]
    c_fc = pal["c1"]
    c_band = pal["cl"]
    c_outlier = "#D84315"  # naranja-rojo apagado (daltonism-friendly)
    c_div = "#555555"
    c_gray = conf_paleta["cool_gray"]
    c_text = conf_paleta["neutral_black"]

    # ── Parsear título → suptitle + subtitle ─────────────────────────
    parts = titulo.split(" · ")
    pad_display = (parts[0] if parts else padecimiento).replace("Depresion", "Depresión")
    nivel_label = parts[1] if len(parts) > 1 else ""
    modo_label = (parts[2] if len(parts) > 2 else "").capitalize()
    anio_ini = serie["ds"].min().year
    anio_fin = fecha_max_fc.year

    # ── Figura ───────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 7.5))
    fig.subplots_adjust(bottom=0.13, top=0.89, left=0.055, right=0.975)

    # Título principal y subtítulo
    fig.suptitle(
        f"{pad_display} — Pronóstico Semanal",
        fontsize=16,
        fontweight="bold",
        color=c_text,
        y=0.96,
    )
    ax.set_title(
        f"{nivel_label}  ·  {modo_label}  ·  {anio_ini}–{anio_fin}",
        fontsize=11,
        color=c_gray,
        pad=10,
    )

    # ── 1. Zona de pronóstico (fondo tenue) ─────────────────────────
    ax.axvspan(
        fecha_max_datos,
        fecha_max_fc,
        alpha=0.04,
        color=c_fc,
        zorder=0,
    )

    # ── 2. Franja COVID-19 ──────────────────────────────────────────
    covid_ini = pd.Timestamp(conf_covid["inicio"])
    covid_fin = pd.Timestamp(conf_covid["fin"])
    ax.axvspan(covid_ini, covid_fin, alpha=0.07, color="#E53935", zorder=0)  # type: ignore[arg-type]
    mid_covid = covid_ini + (covid_fin - covid_ini) / 2
    ax.annotate(
        "COVID-19",
        xy=(mid_covid, 1.0),  # type: ignore[arg-type]
        xycoords=("data", "axes fraction"),
        fontsize=7,
        fontweight="bold",
        color="#C62828",
        ha="center",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.25",
            fc="#FFEBEE",
            ec="#EF9A9A",
            alpha=0.85,
            lw=0.6,
        ),
    )

    # ── 3. Banda de predicción ──────────────────────────────────────
    ax.fill_between(
        forecast["ds"],
        forecast["yhat_lower"],
        forecast["yhat_upper"],
        alpha=0.20,
        color=c_band,
        zorder=1,
        label="Intervalo 80 %",
    )

    # ── 4. Observaciones reales (puntos pequeños) ────────────────────
    ax.scatter(
        serie["ds"],
        serie["y"],
        s=15,
        color=c_obs,
        alpha=0.45,
        zorder=3,
        label="Observaciones reales",
    )

    # ── 5. Línea de pronóstico Prophet (dominante) ───────────────────
    ax.plot(
        forecast["ds"],
        forecast["yhat"],
        color=c_fc,
        linewidth=2.2,
        zorder=4,
        label="Pronóstico Prophet",
    )

    # ── 6. Outliers (triángulos con borde blanco) ────────────────────
    if len(outliers) > 0:
        ax.scatter(
            outliers["ds"],
            outliers["y"],
            marker="^",
            s=45,
            color=c_outlier,
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label=f"Outliers IQR (n = {len(outliers)})",
        )

    # ── 7. Divisor datos históricos / pronóstico ─────────────────────
    _anotar_divisores(ax, fecha_max_datos, c_div, c_fc)

    # ── 8. Zona de prueba CV (sombra gris + etiquetas) ─────────────
    _anotar_zona_cv(ax, fecha_max_datos, c_gray)

    # ── Formato de ejes ──────────────────────────────────────────────
    ax.set_xlabel("")
    ax.set_ylabel("Incrementos semanales", fontsize=11, color=c_text)
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=0.25, color=c_gray, linestyle="-", linewidth=0.5)
    ax.xaxis.grid(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="both", labelsize=10, colors=c_text)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(c_gray)
        ax.spines[spine].set_linewidth(0.5)

    # ── Leyenda + ficha: banda compacta bajo el eje X ───────────────
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.515, 0.04),
        ncol=len(handles),
        fontsize=9.5,
        frameon=False,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=2.0,
    )

    # Ficha técnica: una línea justo debajo de la leyenda
    if metricas:
        _render_ficha_tecnica(fig, metricas)

    # ── Guardar ──────────────────────────────────────────────────────
    ruta = os.path.join(carpeta_salida, f"{nombre_archivo}.png")
    fig.savefig(ruta, dpi=VIZ_DPI_SCREEN, facecolor="white", edgecolor="none")
    plt.close(fig)
    return ruta
