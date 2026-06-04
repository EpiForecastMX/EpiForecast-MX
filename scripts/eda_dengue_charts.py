#!/usr/bin/env python
"""eda_dengue_charts.py — Galería de gráficos EDA del Dengue para la web.

Genera visualizaciones exploratorias profesionales (heatmaps, boxplots, violines,
matriz de correlación y autocorrelación) a partir de la serie validada
``data/interim/dengue_boletin.csv``. Tema Clinical Indigo (fondo índigo), pensadas
para verificar visualmente la calidad y los patrones del dato antes de modelar.

Salidas (PNG) en ``--out`` (por defecto Reports/dengue del repo dashboard):
    eda_heatmap_estado_anio.png  — intensidad por entidad × año
    eda_heatmap_semana_anio.png  — estacionalidad: semana × año (nacional)
    eda_box_anio.png             — distribución de casos semanales por año (boxplot)
    eda_violin_estado.png        — distribución por entidad (violín, top de carga)
    eda_correlacion.png          — matriz de correlación de variables
    eda_acf.png                  — autocorrelación de la serie nacional

Uso:
    python scripts/eda_dengue_charts.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from statsmodels.tsa.stattools import acf  # noqa: E402

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.utils.config import logger  # noqa: E402
from epiforecast.visualization.web_theme import (  # noqa: E402
    AMBER,
    BG,
    GRID,
    MINT,
    MUTED,
    PINK,
    SEMANAS_ANIO,
    TEXT,
    dark_fig,
)

WEEKS = SEMANAS_ANIO
_new = dark_fig  # alias: figura con tema Clinical Indigo (sin grid; seaborn lo maneja)


def _save(fig: plt.Figure, ax: plt.Axes, out: Path, name: str, title: str) -> None:
    ax.set_title(title, fontsize=12, pad=12, color=TEXT)
    fig.tight_layout()
    fig.savefig(out / name, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def heatmap_estado_anio(df: pd.DataFrame, out: Path) -> None:
    piv = df.pivot_table("Casos_semana", "Entidad", "Anio", aggfunc="sum", fill_value=0)
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = _new((9, 10))
    sns.heatmap(
        piv,
        ax=ax,
        cmap="magma",
        annot=True,
        fmt=".0f",
        annot_kws={"size": 7},
        linewidths=0.4,
        linecolor=BG,
        cbar_kws={"label": "Casos confirmados"},
    )
    ax.figure.axes[-1].yaxis.label.set_color(MUTED)
    ax.figure.axes[-1].tick_params(colors=MUTED)
    ax.set_xlabel("")
    ax.set_ylabel("")
    for t in ax.get_yticklabels():
        t.set_color(TEXT)
    _save(
        fig,
        ax,
        out,
        "eda_heatmap_estado_anio.png",
        "Casos de Dengue por entidad y año (entidades ordenadas por carga total)",
    )


def heatmap_semana_anio(df: pd.DataFrame, out: Path) -> None:
    nac = df.copy()
    nac["wk"] = nac["Semana"].astype(int)
    piv = nac.pivot_table("Casos_semana", "wk", "Anio", aggfunc="sum", fill_value=0)
    fig, ax = _new((8, 9))
    sns.heatmap(piv, ax=ax, cmap="rocket", linewidths=0, cbar_kws={"label": "Casos nacionales"})
    ax.figure.axes[-1].yaxis.label.set_color(MUTED)
    ax.figure.axes[-1].tick_params(colors=MUTED)
    ax.set_xlabel("Año")
    ax.set_ylabel("Semana epidemiológica")
    _save(
        fig,
        ax,
        out,
        "eda_heatmap_semana_anio.png",
        "Estacionalidad: casos nacionales por semana × año (la carga vive en sem. 27-52)",
    )


def box_anio(df: pd.DataFrame, out: Path) -> None:
    fig, ax = _new((10, 4.6))
    sns.boxplot(
        data=df,
        x="Anio",
        y="Casos_semana",
        ax=ax,
        color=MINT,
        fliersize=2,
        linewidth=1.1,
        flierprops={"markerfacecolor": PINK, "markeredgecolor": PINK},
    )
    ax.set_yscale("symlog")
    ax.set_xlabel("Año")
    ax.set_ylabel("Casos por semana (escala symlog)")
    _save(
        fig,
        ax,
        out,
        "eda_box_anio.png",
        "Distribución de casos semanales por entidad, por año (boxplot)",
    )


def violin_estado(df: pd.DataFrame, out: Path, top: int = 10) -> None:
    orden = df.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
    estados = orden.head(top).index.tolist()
    sub = df[df["Entidad"].isin(estados)]
    fig, ax = _new((11, 5))
    sns.violinplot(
        data=sub,
        x="Entidad",
        y="Casos_semana",
        order=estados,
        ax=ax,
        color=AMBER,
        inner="box",
        cut=0,
        linewidth=1.0,
    )
    ax.set_yscale("symlog")
    ax.set_xlabel("")
    ax.set_ylabel("Casos por semana (escala symlog)")
    for t in ax.get_xticklabels():
        t.set_rotation(35)
        t.set_ha("right")
    _save(
        fig,
        ax,
        out,
        "eda_violin_estado.png",
        f"Distribución de casos semanales por entidad (violín, top {top} por carga)",
    )


def correlacion(df: pd.DataFrame, out: Path) -> None:
    d = df.copy()
    d["Semana"] = d["Semana"].astype(int)
    cols = {
        "Casos_semana": "Casos sem.",
        "Acumulado_hombres": "Acum. H",
        "Acumulado_mujeres": "Acum. M",
        "Acumulado_anio_anterior": "Acum. año ant.",
        "Semana": "Semana epi.",
    }
    corr = d[list(cols)].rename(columns=cols).corr()
    fig, ax = _new((6.5, 5.5))
    sns.heatmap(
        corr,
        ax=ax,
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
        center=0,
        annot=True,
        fmt=".2f",
        annot_kws={"size": 9, "color": TEXT},
        linewidths=0.5,
        linecolor=BG,
        cbar_kws={"label": "Correlación"},
    )
    ax.figure.axes[-1].yaxis.label.set_color(MUTED)
    ax.figure.axes[-1].tick_params(colors=MUTED)
    for t in ax.get_yticklabels() + ax.get_xticklabels():
        t.set_color(TEXT)
    _save(fig, ax, out, "eda_correlacion.png", "Matriz de correlación de variables (Dengue)")


def acf_nacional(df: pd.DataFrame, out: Path, nlags: int = 60) -> None:
    nac = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    nac["wk"] = nac["Semana"].astype(int)
    serie = nac.sort_values(["Anio", "wk"])["Casos_semana"].to_numpy(dtype=float)
    vals = acf(serie, nlags=nlags, fft=True)
    ci = 1.96 / np.sqrt(len(serie))
    fig, ax = _new((11, 4.4))
    ax.vlines(range(len(vals)), 0, vals, color=MINT, linewidth=1.4)
    ax.scatter(range(len(vals)), vals, color=AMBER, s=14, zorder=5)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.axhline(ci, color=PINK, linestyle="--", linewidth=0.8)
    ax.axhline(-ci, color=PINK, linestyle="--", linewidth=0.8)
    ax.axvline(WEEKS, color=GRID, linewidth=1.0)
    ax.text(WEEKS, ax.get_ylim()[1] * 0.9, " ciclo anual (52)", color=MUTED, fontsize=8)
    ax.set_xlabel("Rezago (semanas)")
    ax.set_ylabel("Autocorrelación")
    _save(
        fig,
        ax,
        out,
        "eda_acf.png",
        "Autocorrelación de la serie nacional (lag-1 alto = serie muy pronosticable)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=None, help="Override del CSV; por defecto el consolidado")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    df = cargar_boletin_dengue(args.csv)
    df["Entidad"] = df["Entidad"].replace(ENTIDAD_DISPLAY)  # display: México -> Estado de México
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="dark")
    heatmap_estado_anio(df, out)
    heatmap_semana_anio(df, out)
    box_anio(df, out)
    violin_estado(df, out)
    correlacion(df, out)
    acf_nacional(df, out)
    logger.success("Galería EDA de Dengue generada en {} (6 gráficos)", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
