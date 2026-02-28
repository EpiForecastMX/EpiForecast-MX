# src/epiforecast/visualization/comparison_plots.py
"""Comparison visualization: Real vs Prophet vs DeepAR.

Professional styling with high-contrast line differentiation.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.forecast_plots import _normalizar_nombre

# ── Layout constants ─────────────────────────────────────────────────
_FIGSIZE = (16, 8)
_Y_MARGIN_BOTTOM = 0.85
_Y_MARGIN_TOP = 1.15

# ── Colors ───────────────────────────────────────────────────────────
_COLOR_REAL = "lightgray"
_COLOR_PROPHET = "#004d40"  # teal
_COLOR_DEEPAR = "#880e4f"  # vino / burgundy
_COLOR_DIVIDER = "#555555"

# ── Font sizes ───────────────────────────────────────────────────────
_FS_TITLE = 16
_FS_YLABEL = 12
_FS_LEGEND = 10
_FS_TIMESTAMP = 8.5

# ── Model display names ─────────────────────────────────────────────
_MODEL_DISPLAY = {"prophet": "Prophet", "deepar": "DeepAR"}

# ── Timezone ─────────────────────────────────────────────────────────
_TZ_CDMX = ZoneInfo("America/Mexico_City")


def generar_graficos_comparativos(config: dict | None = None) -> None:
    """Genera graficos con alta diferenciacion visual entre modelos."""
    _conf = config if config is not None else conf

    forecast_base = Path(_conf["paths"]["reports"]) / "forecasts"
    output_dir = forecast_base / "comparacion_modelos"
    directory_manager.asegurar_ruta(output_dir)

    path_prophet = forecast_base / "prophet" / "all_forecast_prophet.csv"
    path_deepar = forecast_base / "deepar" / "all_forecast_deepar.csv"

    if not path_prophet.exists() or not path_deepar.exists():
        logger.error("No se pueden comparar modelos: faltan archivos CSV.")
        return

    df_p = pd.read_csv(path_prophet, low_memory=False)
    df_d = pd.read_csv(path_deepar, low_memory=False)

    df_p["ds"] = pd.to_datetime(df_p["ds"])
    df_d["ds"] = pd.to_datetime(df_d["ds"])

    logger.info("Generando comparativas de alto contraste en {}...", output_dir)

    grupos = df_p.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"])

    count = 0
    for (pad_, ent_, modo_), group_p in grupos:
        pad = str(pad_)
        ent = "" if ent_ is None or (isinstance(ent_, float) and np.isnan(ent_)) else str(ent_)
        modo = str(modo_)
        ent_val = ent

        mask_d = (
            (df_d["meta_padecimiento"] == pad)
            & (df_d["meta_entidad"].fillna("") == ent_val)
            & (df_d["meta_modo"] == modo)
        )
        group_d = df_d[mask_d]

        if group_d.empty:
            continue

        pad_norm = _normalizar_nombre(pad)
        ent_norm = _normalizar_nombre(ent_val if ent_val and ent_val.lower() != "nacional" else "")
        csv_name = f"Prophet_{pad_norm}_{ent_norm + '_' if ent_norm else ''}{modo}.csv"
        csv_path = Path(_conf["paths"]["models"]).parent / "prophet" / pad_norm / csv_name

        if not csv_path.exists():
            continue

        serie_real = pd.read_csv(csv_path)
        serie_real["ds"] = pd.to_datetime(serie_real["ds"])
        target_y = (
            serie_real["y_original"] if "y_original" in serie_real.columns else serie_real["y"]
        )

        fig, ax = _render_comparison(serie_real, target_y, group_p, group_d, pad, ent_val, modo)

        safe_ent = _normalizar_nombre(ent_val if ent_val else "Nacional")
        nombre = f"CMP_{pad}_{safe_ent}_{modo}.png"
        pad_dir = output_dir / pad_norm
        directory_manager.asegurar_ruta(pad_dir)
        plt.savefig(pad_dir / nombre, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
        plt.close(fig)
        count += 1

    logger.success("Se generaron {} comparativas de alto contraste en: {}", count, output_dir)


def _render_comparison(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    group_p: pd.DataFrame,
    group_d: pd.DataFrame,
    pad: str,
    ent_val: str,
    modo: str,
) -> tuple[plt.Figure, plt.Axes]:
    """Renderiza un grafico comparativo individual."""
    fig, ax = plt.subplots(figsize=_FIGSIZE)

    # 1. Historial Real
    ax.plot(
        serie_real["ds"],
        target_y,
        color=_COLOR_REAL,
        alpha=1.0,
        linewidth=3.0,
        label="Historial Real",
        zorder=1,
    )

    # 2. Prophet
    ax.plot(
        group_p["ds"],
        group_p["yhat"],
        color=_COLOR_PROPHET,
        linestyle="-.",
        linewidth=1.5,
        alpha=0.8,
        label="Prophet",
        zorder=3,
    )

    # 3. DeepAR
    ax.plot(
        group_d["ds"],
        group_d["yhat"],
        color=_COLOR_DEEPAR,
        linestyle="--",
        linewidth=1.0,
        alpha=0.8,
        label="DeepAR",
        zorder=4,
    )

    # Linea divisoria de inicio de pronostico
    fecha_max_real = serie_real["ds"].max()
    ax.axvline(fecha_max_real, color=_COLOR_DIVIDER, linestyle=":", alpha=0.4, zorder=2)

    # Limites dinamicos de Eje Y
    y_real_vals = np.asarray(target_y.dropna().values).ravel()
    y_p_vals = np.asarray(group_p["yhat"].dropna().values).ravel()
    y_d_vals = np.asarray(group_d["yhat"].dropna().values).ravel()
    all_y = np.concatenate([y_real_vals, y_p_vals, y_d_vals])
    if len(all_y) > 0:
        ax.set_ylim(bottom=np.min(all_y) * _Y_MARGIN_BOTTOM, top=np.max(all_y) * _Y_MARGIN_TOP)

    # Estetica
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Leyenda
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles, strict=False))
    ax.legend(
        by_label.values(),
        by_label.keys(),
        loc="upper left",
        frameon=True,
        shadow=True,
        fontsize=_FS_LEGEND,
    )

    # Titulos
    ent_display = ent_val if ent_val else "Nacional"
    ax.set_title(
        f"Diferenciacion de Modelos: {pad} - {ent_display} ({modo})",
        fontsize=_FS_TITLE,
        fontweight="bold",
        pad=20,
    )
    ax.set_ylabel("Casos Semanales", fontsize=_FS_YLABEL)

    # Marca de tiempo CDMX
    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5,
        0.02,
        f"Generado: {ahora} CDMX  |  EpiForecast-MX",
        ha="center",
        fontsize=_FS_TIMESTAMP,
        color="#808080",
        style="italic",
    )

    return fig, ax
