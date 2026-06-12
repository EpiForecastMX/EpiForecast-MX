# src/epiforecast/visualization/comparison_panels.py
"""Primitivas de paneles para las figuras de comparacion de modelos.

Capas y anotaciones compartidas (banda COVID, linea de corte, zona CV, banda de
pronostico, ficha tecnica, suptitulo) y el merge real/predicho. Sin I/O.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import pandas as pd

from epiforecast.constants import (
    COVID_BADGE_EC,
    COVID_BADGE_FC,
    COVID_END,
    COVID_SPAN_COLOR,
    COVID_START,
    COVID_TEXT_COLOR,
)
from epiforecast.utils.config import conf
from epiforecast.visualization import chart_constants as cc
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
)

_TZ_CDMX = ZoneInfo("America/Mexico_City")
_COVID_START = pd.Timestamp(COVID_START)
_COVID_END = pd.Timestamp(COVID_END)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_covid_band(ax: Axes, *, compact: bool = False) -> None:
    """Add a shaded COVID-19 band with optional badge label."""
    ax.axvspan(
        _COVID_START,
        _COVID_END,
        alpha=cc.ALPHA_COVID,
        color=COVID_SPAN_COLOR,
        zorder=0,
    )
    mid_covid = _COVID_START + (_COVID_END - _COVID_START) / 2
    fs = 5.5 if compact else cc.FS_COVID
    ax.annotate(
        "COVID-19",
        xy=(mid_covid, 1.0),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        fontweight="bold",
        color=COVID_TEXT_COLOR,
        ha="center",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.2",
            fc=COVID_BADGE_FC,
            ec=COVID_BADGE_EC,
            alpha=0.85,
            lw=0.5,
        ),
    )


def _add_cutoff_line(ax: Axes, cutoff: pd.Timestamp, *, compact: bool = False) -> None:
    """Add dashed cutoff line with labels."""
    ax.axvline(
        cutoff,
        color=COLOR_CUTOFF,
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        zorder=7,
    )
    if not compact:
        return
    fs = 6
    ax.annotate(
        "Hist.",
        xy=(cutoff, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        color="#555555",
        ha="right",
        va="top",
    )
    ax.annotate(
        "Pron.",
        xy=(cutoff, 0.96),
        xycoords=("data", "axes fraction"),
        fontsize=fs,
        color=COLOR_CUTOFF,
        ha="left",
        va="top",
    )


def _add_cv_zone(ax: Axes, cutoff: pd.Timestamp, *, compact: bool = False) -> None:
    """Add shaded train/test CV zone."""
    fecha_corte = pd.Timestamp(conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"))
    ax.axvspan(
        fecha_corte,
        cutoff,
        alpha=0.06,
        color="#888888",
        zorder=0,
    )
    ax.axvline(
        fecha_corte,
        color="#888888",
        ls=":",
        lw=0.8,
        alpha=0.6,
        zorder=6,
    )
    if compact:
        fs = 5.5
        ax.annotate(
            "Entren.",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=fs,
            color="#888888",
            ha="right",
            va="top",
        )
        ax.annotate(
            "Prueba CV",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=fs,
            color="#888888",
            ha="left",
            va="top",
        )


def _add_forecast_band(ax: Axes, grp: pd.DataFrame, cutoff: pd.Timestamp, color: str) -> None:
    """Add 80% confidence band in the forecast zone."""
    if "yhat_lower" not in grp.columns or "yhat_upper" not in grp.columns:
        return
    future = grp[grp["ds"] > cutoff]
    if future.empty:
        return
    ax.fill_between(
        future["ds"],
        future["yhat_lower"],
        future["yhat_upper"],
        alpha=0.15,
        color=color,
        zorder=1,
    )


def _stamp(fig: Figure) -> None:
    """Add CDMX timestamp footer."""
    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5,
        0.01,
        f"Generado: {ahora} CDMX  |  EpiForecast-MX",
        ha="center",
        fontsize=8,
        color="#808080",
        style="italic",
    )


def _suptitle(fig: Figure, chart_type: str, pad: str, ent: str, modo: str) -> None:
    """Set a consistent suptitle."""
    ent_display = ent if ent else "Nacional"
    fig.suptitle(
        f"{chart_type}: {pad} - {ent_display} ({modo})",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )


def _merge_real_pred(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    pred: pd.DataFrame,
) -> pd.DataFrame:
    """Merge real and predicted values on date, returning aligned rows."""
    real = pd.DataFrame({"ds": serie_real["ds"], "y_real": target_y.values})
    merged = real.merge(pred[["ds", "yhat"]], on="ds", how="inner")
    return merged.dropna(subset=["y_real", "yhat"])
