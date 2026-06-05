#!/usr/bin/env python
"""dengue_showcase_charts.py — Gráficos de alto impacto para la página de Dengue.

Genera dos figuras (tema Clinical Indigo) para la web:
  - ``dengue_mapa_mexico.png``     mapa coroplético: carga de dengue por entidad (2018-2026).
  - ``dengue_historico_ciclo.png`` total anual confirmado 2014-2026 (A90/A91 + A97.x),
                                   marcando el ciclo epidémico (cuatro a cinco años: 2014, 2019, 2024).

Uso:
    python scripts/dengue_showcase_charts.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
from pathlib import Path
import unicodedata
import warnings

import geopandas as gpd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LogNorm
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")

from epiforecast.constants import COVID_END, COVID_START  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.visualization.web_theme import (  # noqa: E402
    AMBER,
    BG,
    DPI,
    GRID,
    MINT,
    MUTED,
    PINK,
    TEXT,
)

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "data" / "utils" / "mexico_states.geojson"
A9091 = ROOT / "data" / "interim" / "dengue_a90a91_nacional.csv"

# Colormap de marca: pocos casos (índigo) -> mint -> ámbar -> rosa caliente (brote).
DENGUE_CMAP = LinearSegmentedColormap.from_list("dengue", ["#1B2742", MINT, AMBER, PINK])
_SIN_CASOS = "#2A3550"  # estados sin transmisión confirmada
_PEAK_YEARS = {2014, 2019, 2024}


def _year_frac(iso: str) -> float:
    """Fecha ISO -> año fraccional (para alinear con un eje de años)."""
    d = pd.Timestamp(iso)
    return d.year + (d.dayofyear - 1) / 365


def _norm(s: str) -> str:
    return (
        "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
        .strip()
        .lower()
    )


def chart_mapa_mexico(out: Path) -> None:
    """Mapa coroplético: total de dengue confirmado por entidad (2018-2026)."""
    df = cargar_boletin_dengue()
    tot = df.groupby("Entidad")["Casos_semana"].sum().reset_index()
    tot["k"] = tot["Entidad"].map(_norm)

    gdf = gpd.read_file(GEOJSON)
    gdf["k"] = gdf["name"].map(_norm)
    gdf = gdf.merge(tot[["k", "Casos_semana"]], on="k", how="left")
    gdf["casos"] = gdf["Casos_semana"].fillna(0)
    gdf["plot_val"] = gdf["casos"].where(gdf["casos"] > 0)  # LogNorm no admite 0

    vmax = float(gdf["casos"].max())
    vmin = float(gdf.loc[gdf["casos"] > 0, "casos"].min())

    fig, ax = plt.subplots(figsize=(10.5, 8), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    norm = LogNorm(vmin=vmin, vmax=vmax)
    gdf.plot(
        column="plot_val",
        cmap=DENGUE_CMAP,
        norm=norm,
        ax=ax,
        edgecolor="#0E1424",
        linewidth=0.6,
        missing_kwds={"color": _SIN_CASOS, "edgecolor": "#0E1424", "linewidth": 0.6},
    )
    ax.set_axis_off()
    # Márgenes amplios para que las etiquetas con línea guía no se recorten en los bordes.
    minx, miny, maxx, maxy = gdf.total_bounds
    ax.set_xlim(minx - (maxx - minx) * 0.16, maxx + (maxx - minx) * 0.10)
    ax.set_ylim(miny - (maxy - miny) * 0.08, maxy + (maxy - miny) * 0.05)
    ax.set_title(
        "¿Dónde golpea el dengue? Casos confirmados por entidad (2018-2026)",
        color=TEXT,
        fontsize=13.5,
        pad=16,
        fontweight="bold",
    )

    # Etiquetas de los estados de mayor carga: centradas dentro del polígono (son grandes).
    for _, r in gdf.nlargest(4, "casos").iterrows():
        c = r.geometry.representative_point()
        ax.annotate(
            f"{r['name']}\n{int(r['casos']):,}",
            xy=(c.x, c.y),
            ha="center",
            va="center",
            fontsize=8,
            color="#0E1424",
            fontweight="bold",
            zorder=5,
        )
    # Estados en cero (centro, pequeños y juntos): etiqueta con línea guía hacia afuera, a
    # zonas vacías del lienzo, para que no se encimen entre sí ni se recorten en el borde.
    leader = {
        "ciudad de mexico": (-7.5, -2.6),  # hacia el Pacífico (abajo-izquierda)
        "tlaxcala": (6.5, 2.4),  # hacia el Golfo (arriba-derecha)
    }
    for _, r in gdf[gdf["casos"] == 0].iterrows():
        c = r.geometry.representative_point()
        dx, dy = leader.get(r["k"], (6, 4))
        ax.annotate(
            f"{r['name']} · sin casos",
            xy=(c.x, c.y),
            xytext=(c.x + dx, c.y + dy),
            ha="center",
            va="center",
            fontsize=8,
            color=TEXT,
            fontweight="bold",
            zorder=5,
            clip_on=False,
            arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8},
        )

    sm = ScalarMappable(norm=norm, cmap=DENGUE_CMAP)
    cb = fig.colorbar(sm, ax=ax, fraction=0.028, pad=0.01)
    cb.set_label("Casos confirmados (escala logarítmica)", color=MUTED, fontsize=9)
    cb.ax.tick_params(colors=MUTED, labelsize=8)
    cb.outline.set_edgecolor(GRID)
    fig.text(
        0.5,
        0.045,
        "Carga concentrada en el sureste tropical y las costas; el centro-altiplano "
        "(Ciudad de México, Tlaxcala) sin transmisión confirmada.",
        ha="center",
        color=MUTED,
        fontsize=9,
    )
    # right=0.95 deja aire para las etiquetas del colorbar; bbox_inches="tight" garantiza
    # que no se recorte el "10^x" del borde derecho (antes right=0.98 las cortaba).
    fig.subplots_adjust(top=0.93, bottom=0.09, left=0.02, right=0.95)
    fig.savefig(out / "dengue_mapa_mexico.png", facecolor=BG, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def chart_historico_ciclo(out: Path) -> None:
    """Total anual confirmado 2014-2026 marcando el ciclo epidémico (cuatro a cinco años)."""
    old = pd.read_csv(A9091)
    old["tot"] = old["Acumulado_hombres"] + old["Acumulado_mujeres"]
    old_y = old.groupby("Anio")["tot"].max()  # acumulado de fin de año
    new = cargar_boletin_dengue().groupby("Anio")["Casos_semana"].sum()

    last_year = int(max(new.index.max(), old_y.index.max()))
    years = list(range(2014, last_year + 1))  # 2014 = inicio A90/A91; tope desde el dato
    vals = [int(new[y]) if y in new.index else int(old_y.get(y, 0)) for y in years]
    colors = [PINK if y in _PEAK_YEARS else MINT for y in years]
    ymax = max(vals)

    fig, ax = plt.subplots(figsize=(11.5, 5.4), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    # Franja COVID-19 (fechas oficiales del proyecto, COVID_START/COVID_END en constants), en
    # fracción de año para alinear con el eje. El dengue siguió su ciclo natural pese a ella.
    covid_ini, covid_fin = _year_frac(COVID_START), _year_frac(COVID_END)
    ax.axvspan(covid_ini, covid_fin, color="#5B8DEF", alpha=0.10, zorder=1)
    ax.text(
        (covid_ini + covid_fin) / 2,
        ymax * 1.02,
        "COVID-19",
        ha="center",
        fontsize=7.5,
        color="#7FA0E0",
        style="italic",
        zorder=2,
    )
    ax.bar(years, vals, color=colors, edgecolor="#0E1424", linewidth=0.8, zorder=3)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6, alpha=0.5, zorder=0)
    ax.set_ylabel("Casos confirmados en el año", color=MUTED)
    ax.set_xticks(years)
    ax.set_ylim(0, ymax * 1.20)  # headroom para que las etiquetas no toquen el título

    for x, v in zip(years, vals, strict=True):
        ax.annotate(
            f"{v:,}",
            xy=(x, v),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=7.8,
            color=(PINK if x in _PEAK_YEARS else MUTED),
            fontweight=("bold" if x in _PEAK_YEARS else "normal"),
        )

    ax.set_title(
        "El dengue vuelve en olas: grandes brotes cada cuatro a cinco años (2014 · 2019 · 2024)",
        color=TEXT,
        fontsize=13.5,
        pad=14,
        fontweight="bold",
    )
    # Transición de taxonomía: línea y etiqueta arriba, en zona vacía (sin tocar barras).
    ax.axvline(2017.5, color=MUTED, linestyle=":", linewidth=1, alpha=0.7, zorder=2)
    ax.text(
        2015.5,
        ymax * 1.12,
        "OMS 1997 (A90/A91)",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    ax.text(
        2022,
        ymax * 1.12,
        "OMS 2009 (A97.x)",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    fig.text(
        0.5,
        0.065,
        "Los picos (2014, 2019, 2024) coinciden con años de El Niño (mayor temperatura, "
        "más transmisión); 2024 fue la mayor epidemia de dengue registrada en las Américas.",
        ha="center",
        color=TEXT,
        fontsize=8.6,
    )
    fig.text(
        0.5,
        0.018,
        "Fuente: OPS/PAHO, Actualización Epidemiológica de Dengue (2024) · SINAVE/DGE. "
        "2014-2017: A90/A91 confirmado; 2018-2026: A97.x agregado; 2026 parcial.",
        ha="center",
        color=MUTED,
        fontsize=7.6,
    )
    fig.subplots_adjust(top=0.88, bottom=0.16)
    fig.savefig(out / "dengue_historico_ciclo.png", facecolor=BG)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chart_mapa_mexico(out)
    chart_historico_ciclo(out)
    print(f"Showcase charts de Dengue generados en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
