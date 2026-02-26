"""Forecast chart annotation helpers: divisors, CV zones, and model metrics card."""

import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.utils.config import conf


def _anotar_divisores(
    ax: plt.Axes,
    fecha_max_datos,
    c_div: str,
    c_fc: str,
) -> None:
    """Añade la línea vertical y etiquetas de separación datos/pronóstico."""
    ax.axvline(
        fecha_max_datos,
        color=c_div,
        ls="--",
        lw=1.5,
        alpha=0.7,
        zorder=6,
    )
    ax.annotate(
        "← Datos históricos ",
        xy=(fecha_max_datos, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=9.5,
        fontweight="semibold",
        color=c_div,
        ha="right",
        va="top",
    )
    ax.annotate(
        " Pronóstico →",
        xy=(fecha_max_datos, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=9.5,
        fontweight="semibold",
        color=c_fc,
        ha="left",
        va="top",
    )


def _anotar_zona_cv(
    ax: plt.Axes,
    fecha_max_datos,
    c_gray: str,
    config: dict | None = None,
) -> None:
    """Añade la franja sombreada del periodo de prueba CV con etiquetas.

    Args:
        ax:             Axes de matplotlib sobre el que se dibuja.
        fecha_max_datos: Fecha máxima de datos históricos.
        c_gray:         Color para la franja y líneas.
        config:         Dict de configuración (default: conf global de YAML).
    """
    _conf = config if config is not None else conf
    fecha_corte = pd.Timestamp(_conf["FECHA_CORTE_ENTRENAMIENTO"])

    ax.axvspan(
        fecha_corte,  # type: ignore[arg-type]
        fecha_max_datos,
        alpha=0.06,
        color=c_gray,
        zorder=0,
    )
    ax.axvline(
        fecha_corte,  # type: ignore[arg-type]
        color=c_gray,
        ls=":",
        lw=1.2,
        alpha=0.6,
        zorder=6,
    )
    ax.annotate(
        "Entrenamiento",
        xy=(fecha_corte, 0.88),  # type: ignore[arg-type]
        xycoords=("data", "axes fraction"),
        fontsize=7.5,
        color=c_gray,
        ha="right",
        va="top",
    )
    ax.annotate(
        "Prueba CV",
        xy=(fecha_corte, 0.88),  # type: ignore[arg-type]
        xycoords=("data", "axes fraction"),
        fontsize=7.5,
        color=c_gray,
        ha="left",
        va="top",
    )


def _render_ficha_tecnica(fig: plt.Figure, metricas: dict) -> None:
    """Renderiza la ficha técnica del modelo al pie del gráfico."""
    mase_v = metricas.get("mase")
    rmse_v = metricas.get("rmse")
    confianza = metricas.get("confianza", "normal")
    es_fallback = metricas.get("es_fallback", False)
    modelo_usado = metricas.get("modelo_usado", "")

    tokens = ["Prophet (Meta/Facebook)", "IC 80 %"]

    if mase_v is not None and mase_v < 100:
        tag = "supera naive" if mase_v < 1 else "no supera naive"
        tokens.append(f"MASE: {mase_v:.2f} ({tag})")
    if rmse_v is not None and rmse_v < 100:
        tokens.append(f"RMSE: {rmse_v:.4f}")

    if es_fallback:
        region = ""
        if "region_" in modelo_usado:
            region = modelo_usado.split("region_")[1].rsplit("_", 1)[0]
            region = region.replace("_", " ").replace("-", "/")
        tokens.append(f"Modelo: Regional ({region})" if region else "Modelo: Regional (respaldo)")
    elif confianza == "normal":
        tokens.append("Modelo: Estatal propio")

    if metricas.get("seasonality_mode"):
        tokens.append(f"Estac: {metricas['seasonality_mode']}")
    if metricas.get("changepoint_prior_scale") is not None:
        tokens.append(f"CP: {metricas['changepoint_prior_scale']}")
    if metricas.get("seasonality_prior_scale") is not None:
        tokens.append(f"SP: {metricas['seasonality_prior_scale']}")

    ficha = "  |  ".join(tokens)
    fig.text(
        0.515,
        0.008,
        ficha,
        ha="center",
        va="bottom",
        fontsize=8.5,
        family="sans-serif",
        color="#999",
    )
