# src/epiforecast/visualization/avance5_panels.py
"""Primitivas de panel para los graficos del Avance 5 (capas/anotaciones). Sin I/O."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import pandas as pd

from epiforecast.constants import COVID_END, COVID_START
from epiforecast.visualization.comparison_config import (
    COLOR_CUTOFF,
    COVID_FILL,
)

_TZ_CDMX = ZoneInfo("America/Mexico_City")
_COVID_START = pd.Timestamp(COVID_START)
_COVID_END = pd.Timestamp(COVID_END)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _covid_band(ax: Axes) -> None:
    ax.axvspan(
        _COVID_START.to_pydatetime(),
        _COVID_END.to_pydatetime(),
        color=COVID_FILL,
        alpha=0.5,
        zorder=0,
    )


def _cutoff_line(ax: Axes, cutoff: pd.Timestamp) -> None:
    ax.axvline(
        cutoff.to_pydatetime(),
        color=COLOR_CUTOFF,
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        zorder=7,
    )


def _clean_spines(ax: Axes) -> None:
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)


def _stamp(fig: Figure) -> None:
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
