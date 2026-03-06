"""Forecast chart annotation helpers: divisors, CV zones, and model metrics card."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import pandas as pd

from epiforecast.utils.config import conf

_TZ_CDMX = ZoneInfo("America/Mexico_City")

# ── Annotation styling ───────────────────────────────────────────────
_LW_DIVIDER = 1.5
_ALPHA_DIVIDER = 0.7
_FS_DIVIDER = 9.5
_Y_DIVIDER = 0.96

_ALPHA_CV_ZONE = 0.06
_LW_CV_LINE = 1.2
_ALPHA_CV_LINE = 0.6
_FS_CV_LABEL = 7.5
_Y_CV_LABEL = 0.88

_FS_FICHA = 8.5
_FICHA_X = 0.515
_FICHA_Y = 0.008

_MODEL_DISPLAY: dict[str, str] = {
    "prophet": "Prophet (Meta/Facebook)",
    "deepar": "DeepAR (Amazon)",
    "ensemble": "Ensemble (Prophet + XGBoost)",
    "stacking": "Stacking (Prophet + ETS + LightGBM)",
}


def _anotar_divisores(
    ax: Axes,
    fecha_max_datos: pd.Timestamp,
    c_div: str,
    c_fc: str,
) -> None:
    """Añade la línea vertical y etiquetas de separación datos/pronóstico."""
    ax.axvline(
        fecha_max_datos,
        color=c_div,
        ls="--",
        lw=_LW_DIVIDER,
        alpha=_ALPHA_DIVIDER,
        zorder=6,
    )
    ax.annotate(
        "← Datos históricos ",
        xy=(fecha_max_datos, _Y_DIVIDER),
        xycoords=("data", "axes fraction"),
        fontsize=_FS_DIVIDER,
        fontweight="semibold",
        color=c_div,
        ha="right",
        va="top",
    )
    ax.annotate(
        " Inicio pronóstico →",
        xy=(fecha_max_datos, _Y_DIVIDER),
        xycoords=("data", "axes fraction"),
        fontsize=_FS_DIVIDER,
        fontweight="semibold",
        color=c_fc,
        ha="left",
        va="top",
    )


def _anotar_zona_cv(
    ax: Axes,
    fecha_max_datos: pd.Timestamp,
    c_gray: str,
    config: dict[str, Any] | None = None,
) -> None:
    """Añade la franja sombreada del periodo de prueba CV con etiquetas.

    Args:
        ax:             Axes de matplotlib sobre el que se dibuja.
        fecha_max_datos: Fecha máxima de datos históricos.
        c_gray:         Color para la franja y líneas.
        config:         Dict de configuración (default: conf global de YAML).
    """
    _conf = config if config is not None else conf
    # pd.Timestamp → matplotlib: stubs incompletos, funciona en runtime
    fecha_corte = pd.Timestamp(_conf["FECHA_CORTE_ENTRENAMIENTO"]).to_pydatetime()

    ax.axvspan(
        fecha_corte,
        fecha_max_datos,
        alpha=_ALPHA_CV_ZONE,
        color=c_gray,
        zorder=0,
    )
    ax.axvline(
        fecha_corte,
        color=c_gray,
        ls=":",
        lw=_LW_CV_LINE,
        alpha=_ALPHA_CV_LINE,
        zorder=6,
    )
    ax.annotate(
        "Entrenamiento",
        xy=(fecha_corte, _Y_CV_LABEL),
        xycoords=("data", "axes fraction"),
        fontsize=_FS_CV_LABEL,
        color=c_gray,
        ha="right",
        va="top",
    )
    ax.annotate(
        "Prueba CV",
        xy=(fecha_corte, _Y_CV_LABEL),
        xycoords=("data", "axes fraction"),
        fontsize=_FS_CV_LABEL,
        color=c_gray,
        ha="left",
        va="top",
    )


def _render_ficha_tecnica(fig: Figure, metricas: dict[str, Any]) -> None:
    """Renderiza la ficha tecnica del modelo al pie del grafico."""
    mase_v = metricas.get("mase")
    rmse_v = metricas.get("rmse")
    smape_v = metricas.get("smape")
    mae_v = metricas.get("mae")
    mape_v = metricas.get("mape")
    confianza = metricas.get("confianza", "normal")
    es_fallback = metricas.get("es_fallback", False)
    modelo_usado = metricas.get("modelo_usado", "")

    # Detectar modelo real: meta_modelo > filename > config fallback
    meta_modelo = str(metricas.get("meta_modelo", "")).lower()
    if not meta_modelo and modelo_usado and "_" in modelo_usado:
        meta_modelo = modelo_usado.split("_")[0].lower()
    if not meta_modelo:
        meta_modelo = conf.get("modelo_activo", "prophet").lower()

    display_name = _MODEL_DISPLAY.get(meta_modelo, meta_modelo.capitalize())
    tokens = [display_name, "IC 80 %"]

    # Todas las metricas disponibles
    if smape_v is not None and smape_v < 999:
        tokens.append(f"SMAPE: {smape_v:.2f}%")
    if mase_v is not None:
        tag = "supera naive" if mase_v < 1 else "no supera naive"
        tokens.append(f"MASE: {mase_v:.2f} ({tag})")
    if rmse_v is not None and rmse_v < 1e6:
        tokens.append(f"RMSE: {rmse_v:.4f}")
    if mae_v is not None and mae_v < 1e6:
        tokens.append(f"MAE: {mae_v:.4f}")
    if mape_v is not None and mape_v < 999:
        tokens.append(f"MAPE: {mape_v:.2f}%")

    if es_fallback:
        region = ""
        if "region_" in modelo_usado:
            region = modelo_usado.split("region_")[1].rsplit("_", 1)[0]
            region = region.replace("_", " ").replace("-", "/")
        tokens.append(f"Modelo: Regional ({region})" if region else "Modelo: Regional (respaldo)")
    elif confianza == "normal":
        nivel = (
            "Nacional" if "Nacional" in modelo_usado or "_general" in modelo_usado else "Estatal"
        )
        tokens.append(f"Modelo: {nivel} propio")

    # Prophet specific HP
    if meta_modelo == "prophet":
        if metricas.get("seasonality_mode"):
            tokens.append(f"Estac: {metricas['seasonality_mode']}")
        if metricas.get("changepoint_prior_scale") is not None:
            tokens.append(f"CP: {metricas['changepoint_prior_scale']}")
        if metricas.get("seasonality_prior_scale") is not None:
            tokens.append(f"SP: {metricas['seasonality_prior_scale']}")

    # DeepAR specific HP (from config)
    if meta_modelo == "deepar":
        epochs = conf.get("epochs")
        layers = conf.get("num_layers")
        if epochs:
            tokens.append(f"Epochs: {epochs}")
        if layers:
            tokens.append(f"Layers: {layers}")

    ficha = "  |  ".join(tokens)
    fig.text(
        _FICHA_X,
        _FICHA_Y,
        ficha,
        ha="center",
        va="bottom",
        fontsize=_FS_FICHA,
        family="sans-serif",
        color="#999",
    )

    # Marca de tiempo discreta (Hora CDMX)
    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.99,
        0.015,
        f"Generado: {ahora} CDMX",
        ha="right",
        va="bottom",
        fontsize=6.5,
        family="sans-serif",
        color="#b0b0b0",
        style="italic",
    )
