# src/epiforecast/visualization/comparison_plots.py
"""Comparison visualization: Real vs Prophet vs DeepAR vs Ensemble vs Stacking.

Professional styling with high-contrast line differentiation.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.comparison_builders import (
    build_metrics_bars,
    build_overlay,
    build_residuals,
    build_small_multiples,
)
from epiforecast.visualization.forecast_plots import _normalizar_nombre

# -- Layout constants ---------------------------------------------------------
_FIGSIZE = (16, 8)
_Y_MARGIN_BOTTOM = 0.85
_Y_MARGIN_TOP = 1.15

# -- Model visual config (order matters for legend) --------------------------
_MODELS: dict[str, dict[str, object]] = {
    "prophet": {
        "color": "#004d40",
        "linestyle": "-.",
        "linewidth": 1.5,
        "label": "Prophet",
        "zorder": 3,
    },
    "deepar": {
        "color": "#880e4f",
        "linestyle": "--",
        "linewidth": 1.2,
        "label": "DeepAR",
        "zorder": 4,
    },
    "ensemble": {
        "color": "#FF6F00",
        "linestyle": "-",
        "linewidth": 1.2,
        "label": "Ensemble",
        "zorder": 5,
    },
    "stacking": {
        "color": "#1A237E",
        "linestyle": (0, (3, 1, 1, 1)),
        "linewidth": 1.2,
        "label": "Stacking",
        "zorder": 6,
    },
}

_COLOR_REAL = "lightgray"
_COLOR_DIVIDER = "#555555"

# -- Font sizes ---------------------------------------------------------------
_FS_TITLE = 16
_FS_YLABEL = 12
_FS_LEGEND = 10
_FS_TIMESTAMP = 8.5

# -- Timezone -----------------------------------------------------------------
_TZ_CDMX = ZoneInfo("America/Mexico_City")


def generar_graficos_comparativos(config: dict[str, Any] | None = None) -> None:
    """Genera graficos con alta diferenciacion visual entre los 4 modelos."""
    _conf = config if config is not None else conf

    forecast_base = Path(_conf["paths"]["reports"]) / "forecasts"
    output_dir = forecast_base / "comparacion_modelos"
    directory_manager.asegurar_ruta(output_dir)

    # Cargar todos los modelos disponibles
    model_dfs: dict[str, pd.DataFrame] = {}
    for model_key in _MODELS:
        csv_path = forecast_base / model_key / f"all_forecast_{model_key}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, low_memory=False)
            df["ds"] = pd.to_datetime(df["ds"])
            model_dfs[model_key] = df
            logger.info("  Cargado {}: {:,} filas", model_key, len(df))

    if not model_dfs:
        logger.error("No se pueden comparar modelos: no hay archivos CSV de forecast.")
        return

    # Usar el primer modelo disponible como referencia para los grupos
    ref_key = next(iter(model_dfs))
    ref_df = model_dfs[ref_key]

    logger.info("Generando comparativas de alto contraste en {}...", output_dir)

    grupos = ref_df.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"])

    count = 0
    for (pad_, ent_, modo_), _group_ref in grupos:
        pad = str(pad_)
        ent = "" if ent_ is None or (isinstance(ent_, float) and np.isnan(ent_)) else str(ent_)
        modo = str(modo_)

        # Obtener grupo de cada modelo
        groups: dict[str, pd.DataFrame] = {}
        for mk, mdf in model_dfs.items():
            mask = (
                (mdf["meta_padecimiento"] == pad)
                & (mdf["meta_entidad"].fillna("") == ent)
                & (mdf["meta_modo"] == modo)
            )
            grp = mdf[mask]
            if not grp.empty:
                groups[mk] = grp

        if len(groups) < 2:
            continue

        # Obtener serie real desde CSV de Prophet (o el primer modelo disponible)
        serie_real = _load_serie_real(_conf, pad, ent, modo)
        if serie_real is None:
            continue

        target_y = (
            serie_real["y_original"] if "y_original" in serie_real.columns else serie_real["y"]
        )

        fig, ax = _render_comparison(serie_real, target_y, groups, pad, ent, modo)

        safe_ent = _normalizar_nombre(ent if ent else "Nacional")
        pad_norm = _normalizar_nombre(pad)
        base_name = f"{pad}_{safe_ent}_{modo}.png"
        pad_dir = output_dir / pad_norm

        # Grafico principal → subcarpeta "comparativa"
        cmp_dir = pad_dir / "comparativa"
        directory_manager.asegurar_ruta(cmp_dir)
        plt.savefig(cmp_dir / base_name, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
        plt.close(fig)
        count += 1

        # -- 4 graficos adicionales → subcarpetas descriptivas ---------------
        builder_args = (serie_real, target_y, groups, pad, ent, modo)
        extras: list[tuple[str, Figure | None]] = [
            ("paneles_individuales", build_small_multiples(*builder_args)),
            ("overlay", build_overlay(*builder_args)),
            ("metricas", build_metrics_bars(*builder_args)),
            ("residuales", build_residuals(*builder_args)),
        ]
        for subdir_name, extra_fig in extras:
            if extra_fig is None:
                continue
            sub_dir = pad_dir / subdir_name
            directory_manager.asegurar_ruta(sub_dir)
            extra_fig.savefig(sub_dir / base_name, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
            plt.close(extra_fig)

    logger.success("Se generaron {} comparativas de alto contraste en: {}", count, output_dir)


def _load_serie_real(_conf: dict[str, Any], pad: str, ent: str, modo: str) -> pd.DataFrame | None:
    """Busca CSV de serie real en cualquier directorio de modelo disponible."""
    pad_norm = _normalizar_nombre(pad)
    ent_norm = _normalizar_nombre(ent if ent and ent.lower() != "nacional" else "")

    for model_key, prefix in [
        ("prophet", "Prophet"),
        ("ensemble", "Ensemble"),
        ("stacking", "Stacking"),
        ("deepar", "Deepar"),
    ]:
        csv_name = f"{prefix}_{pad_norm}_{ent_norm + '_' if ent_norm else ''}{modo}.csv"
        csv_path = Path(_conf["paths"]["models"]).parent / model_key / pad_norm / csv_name
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df["ds"] = pd.to_datetime(df["ds"])
            return df
    return None


def _render_comparison(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    groups: dict[str, pd.DataFrame],
    pad: str,
    ent_val: str,
    modo: str,
) -> tuple[Figure, Axes]:
    """Renderiza un grafico comparativo individual con N modelos."""
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

    # 2. Cada modelo
    all_yhat: list[npt.NDArray[Any]] = []
    for model_key, style in _MODELS.items():
        if model_key not in groups:
            continue
        grp = groups[model_key]
        ax.plot(
            grp["ds"],
            grp["yhat"],
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=style["linewidth"],
            alpha=0.8,
            label=style["label"],
            zorder=style["zorder"],
        )
        all_yhat.append(np.asarray(grp["yhat"].dropna().values).ravel())

    # Linea divisoria de inicio de pronostico
    fecha_max_real = serie_real["ds"].max()
    ax.axvline(fecha_max_real, color=_COLOR_DIVIDER, linestyle=":", alpha=0.4, zorder=2)

    # Limites dinamicos de Eje Y
    y_real_vals = np.asarray(target_y.dropna().values).ravel()
    all_y = np.concatenate([y_real_vals] + all_yhat) if all_yhat else y_real_vals
    if len(all_y) > 0:
        ax.set_ylim(bottom=np.min(all_y) * _Y_MARGIN_BOTTOM, top=np.max(all_y) * _Y_MARGIN_TOP)

    # Estetica
    ax.xaxis.set_major_locator(mdates.YearLocator())  # type: ignore[no-untyped-call]
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))  # type: ignore[no-untyped-call]
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
        f"Diferenciaci\u00f3n de Modelos: {pad} - {ent_display} ({modo})",
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
