#!/usr/bin/env python
"""build_dengue_web.py — Genera artefactos web de la Fase 1 de Dengue.

A partir de la serie validada (``data/interim/dengue_boletin.csv``) produce:
  - Gráficos preliminares PNG (tema Clinical Indigo, fondo índigo):
      dengue_nacional_semanal.png  — incidencia semanal nacional 2020-2026
      dengue_totales_anuales.png   — casos confirmados por año
      dengue_estacionalidad.png    — climatología por semana epidemiológica
  - ``dengue_serie.json`` — datos para la tabla EN VIVO de la página
      (última semana por entidad + serie nacional + metadatos). La página web
      hace fetch de este JSON, de modo que al regenerarlo y desplegarlo, la
      tabla y las cifras se actualizan solas.

Uso:
    python scripts/build_dengue_web.py \
        --csv data/interim/dengue_boletin.csv \
        --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

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

MESES_SEM = SEMANAS_ANIO
_Z_OUTLIER = 3  # umbral z-score del tratamiento estándar de outliers (ilustrativo en charts)
# Serie histórica A90/A91 (2014-2017, esquema OMS 1997) para extender los totales anuales como
# CONTEXTO (no entra al modelado). Regenerable con `make dengue-historico-a9091`.
A9091 = Path(__file__).resolve().parent.parent / "data" / "interim" / "dengue_a90a91_nacional.csv"


def _fig(figsize: tuple[float, float]) -> tuple[plt.Figure, plt.Axes]:
    """Atajo: figura con tema Clinical Indigo y grid (convención de estos charts)."""
    return dark_fig(figsize, grid=True)


def chart_nacional_semanal(df: pd.DataFrame, out: Path) -> None:
    """Serie de tiempo: casos confirmados de Dengue por semana, nacional."""
    g = df.groupby(["Anio", "Semana"], as_index=False).Casos_semana.sum()
    g["t"] = g.Anio + (g.Semana.astype(int) - 1) / MESES_SEM
    rango = f"{int(df.Anio.min())}-{int(df.Anio.max())}"
    fig, ax = _fig((11, 4.2))
    ax.plot(g.t, g.Casos_semana, color=AMBER, linewidth=1.8)
    ax.fill_between(g.t, g.Casos_semana, color=AMBER, alpha=0.12)
    ax.set_title(
        f"Incidencia semanal nacional de Dengue confirmado ({rango})", fontsize=12, pad=12
    )
    ax.set_ylabel("Casos por semana")
    ax.set_xlabel("Año epidemiológico")
    fig.tight_layout()
    fig.savefig(out / "dengue_nacional_semanal.png", facecolor=BG)
    plt.close(fig)


def chart_totales_anuales(df: pd.DataFrame, out: Path) -> None:
    """Barras: casos confirmados por año, 2014-2026.

    2018-2026 es la serie de modelado (A97.x). 2014-2017 se agrega como CONTEXTO en estilo
    atenuado (esquema viejo A90/A91, otra clasificación, NO entra al entrenamiento), con un
    divisor que marca el cambio. Resalta el pico epidémico 2024.
    """
    g = df.groupby("Anio", as_index=False).Casos_semana.sum()
    nuevos = {int(a): int(v) for a, v in zip(g.Anio, g.Casos_semana, strict=True)}

    contexto: dict[int, int] = {}
    if A9091.exists():
        old = pd.read_csv(A9091)
        old["tot"] = old["Acumulado_hombres"] + old["Acumulado_mujeres"]
        contexto = {int(a): int(v) for a, v in old.groupby("Anio")["tot"].max().items()}

    ini = min([*contexto, *nuevos]) if contexto else int(g.Anio.min())
    fin = int(g.Anio.max())
    years = list(range(ini, fin + 1))
    vals = [nuevos.get(a, contexto.get(a, 0)) for a in years]
    pico = max(years, key=lambda a: nuevos.get(a, 0))  # pico solo entre años de modelado

    def _color(a: int) -> str:
        if a not in nuevos:
            return GRID  # contexto A90/A91 atenuado
        return AMBER if a == pico else MINT

    colors = [_color(a) for a in years]
    fig, ax = _fig((10.5, 4.2))
    bars = ax.bar([str(a) for a in years], vals, color=colors, width=0.66)
    for b, v, a in zip(bars, vals, years, strict=True):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{v:,}",
            ha="center",
            va="bottom",
            color=MUTED if a not in nuevos else TEXT,
            fontsize=8,
        )
    # Divisor entre el contexto (A90/A91) y la serie de modelado (A97.x).
    primer_modelo = min(nuevos)
    if primer_modelo in years and contexto:
        xdiv = years.index(primer_modelo) - 0.5
        ax.axvline(xdiv, color=MUTED, linewidth=0.9, linestyle=":", alpha=0.7)
        ax.text(
            xdiv - 0.1,
            max(vals) * 0.92,
            "contexto · OMS 1997 (A90/A91)",
            ha="right",
            color=MUTED,
            fontsize=7.8,
            style="italic",
        )
        ax.text(
            xdiv + 0.1,
            max(vals) * 0.92,
            "serie de modelado · OMS 2009 (A97.x)",
            ha="left",
            color=MUTED,
            fontsize=7.8,
            style="italic",
        )
    ax.set_title(
        "Casos confirmados de Dengue por año (suma semanal nacional)", fontsize=12, pad=12
    )
    ax.set_ylabel("Casos confirmados")
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out / "dengue_totales_anuales.png", facecolor=BG)
    plt.close(fig)


def chart_estacionalidad(df: pd.DataFrame, out: Path) -> None:
    """Climatología: promedio nacional de casos por semana epidemiológica."""
    nac = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    nac["wk"] = nac["Semana"].astype(int)
    clim = nac.groupby("wk")["Casos_semana"].mean().reset_index()
    rango = f"{int(df.Anio.min())}-{int(df.Anio.max())}"
    fig, ax = _fig((11, 4.0))
    ax.plot(clim["wk"], clim["Casos_semana"], color=MINT, linewidth=2.0, marker="o", markersize=3)
    ax.fill_between(clim["wk"], clim["Casos_semana"], color=MINT, alpha=0.10)
    ax.set_title(
        f"Estacionalidad del Dengue — promedio por semana epidemiológica ({rango})",
        fontsize=12,
        pad=12,
    )
    ax.set_ylabel("Casos promedio por semana")
    ax.set_xlabel("Semana epidemiológica")
    ax.set_xlim(1, 52)
    fig.tight_layout()
    fig.savefig(out / "dengue_estacionalidad.png", facecolor=BG)
    plt.close(fig)


def chart_outliers(df: pd.DataFrame, out: Path, entidad: str = "Veracruz") -> None:
    """Ilustra por qué se desactivan los outliers para Dengue: marca las semanas que
    el tratamiento estándar (z-score > 3) recortaría/medianizaría, que son picos
    epidémicos reales (la señal a pronosticar), no ruido. Ejemplo: una entidad de
    alta carga."""
    g = (
        df[df["Entidad"] == entidad]
        .assign(t=lambda d: d.Anio + (d.Semana.astype(int) - 1) / MESES_SEM)
        .sort_values("t")
    )
    v = g["Casos_semana"].to_numpy(dtype=float)
    mu, sd = v.mean(), v.std(ddof=0)
    z = (v - mu) / (sd if sd > 0 else 1)
    mask = z > _Z_OUTLIER
    fig, ax = _fig((11, 4.2))
    ax.plot(g["t"], v, color=MINT, linewidth=1.5, alpha=0.9)
    ax.scatter(
        g["t"][mask],
        v[mask],
        color=PINK,
        s=42,
        zorder=5,
        label=f"{int(mask.sum())} picos que el FE estándar borraría (z>3)",
    )
    ax.axhline(mu + 3 * sd, color=PINK, linestyle="--", linewidth=1, alpha=0.6)
    ax.set_title(
        f"Por qué desactivamos el recorte de outliers en Dengue — {entidad}", fontsize=12, pad=12
    )
    ax.set_ylabel("Casos por semana")
    ax.set_xlabel("Año epidemiológico")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "dengue_outliers.png", facecolor=BG)
    plt.close(fig)


def chart_fe_comparacion(df: pd.DataFrame, out: Path, entidad: str = "Veracruz") -> None:
    """Gráfico del feature engineering: muestra el efecto de NUESTRA decisión vs el
    tratamiento estándar. Superpone la serie real (picos preservados, lo que hace el FE
    de Dengue) contra la serie que dejaría el recorte de outliers estándar (picos
    aplanados a la mediana). Ilustrativo, sobre casos semanales de una entidad de carga."""
    g = (
        df[df["Entidad"] == entidad]
        .assign(t=lambda d: d.Anio + (d.Semana.astype(int) - 1) / MESES_SEM)
        .sort_values("t")
    )
    real = g["Casos_semana"].to_numpy(dtype=float)
    mu, sd = real.mean(), real.std(ddof=0)
    med = float(pd.Series(real).median())
    clipped = real.copy()
    clipped[(real - mu) / (sd if sd > 0 else 1) > _Z_OUTLIER] = med  # FE estándar: z>3 -> mediana
    fig, ax = _fig((11, 4.2))
    ax.plot(
        g["t"],
        clipped,
        color=MUTED,
        linewidth=1.6,
        linestyle="--",
        label="FE estándar: picos recortados a la mediana",
    )
    ax.plot(
        g["t"],
        real,
        color=AMBER,
        linewidth=1.8,
        label="FE de Dengue: serie real, picos preservados",
    )
    ax.fill_between(g["t"], clipped, real, where=(real > clipped), color=AMBER, alpha=0.12)
    ax.set_title(f"Efecto del feature engineering en Dengue — {entidad}", fontsize=12, pad=12)
    ax.set_ylabel("Casos por semana")
    ax.set_xlabel("Año epidemiológico")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "dengue_fe_comparacion.png", facecolor=BG)
    plt.close(fig)


def build_json(df: pd.DataFrame, out: Path, generado: str) -> dict:
    """Construye el JSON para la tabla en vivo y las cifras de la página."""
    max_anio = int(df.Anio.max())
    last = df[df.Anio == max_anio]
    max_sem = last.Semana.astype(int).max()
    cuadro = (
        last[last.Semana.astype(int) == max_sem]
        .assign(total=lambda d: d.Acumulado_hombres + d.Acumulado_mujeres)
        .sort_values("total", ascending=False)
    )
    tabla = [
        {
            "entidad": ENTIDAD_DISPLAY.get(r.Entidad, r.Entidad),
            "casos_semana": int(r.Casos_semana),
            "acum_hombres": int(r.Acumulado_hombres),
            "acum_mujeres": int(r.Acumulado_mujeres),
            "acum_total": int(r.Acumulado_hombres + r.Acumulado_mujeres),
        }
        for r in cuadro.itertuples()
    ]
    nac = df.groupby(["Anio", "Semana"], as_index=False).Casos_semana.sum()
    serie = [
        {"anio": int(x.Anio), "semana": int(x.Semana), "casos": int(x.Casos_semana)}
        for x in nac.itertuples()
    ]
    data = {
        "meta": {
            "generado": generado,
            "ultima_semana": f"{max_anio}-W{max_sem:02d}",
            "anio": max_anio,
            "semana": int(max_sem),
            "cobertura": f"{int(df.Anio.min())}-{max_anio}",
            "n_boletines": int(df.groupby(["Anio", "Semana"]).ngroups),
            "n_filas": int(len(df)),
            "casos_semana_nacional": int(cuadro["Casos_semana"].sum()),
            "acum_total_nacional": int(cuadro["total"].sum()),
            "nota": "Dengue confirmado agregado (A97.0 + A97.1 + A97.2). Fuente: boletines SINAVE.",
        },
        "cuadro_ultima_semana": tabla,
        "nacional_semanal": serie,
    }
    (out / "dengue_serie.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=None, help="Override del CSV; por defecto el consolidado")
    parser.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    parser.add_argument(
        "--generado", default="", help="Fecha de generación (ISO); vacío = no estampar"
    )
    args = parser.parse_args()

    df = cargar_boletin_dengue(args.csv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    chart_nacional_semanal(df, out)
    chart_totales_anuales(df, out)
    chart_estacionalidad(df, out)
    chart_outliers(df, out)
    chart_fe_comparacion(df, out)
    data = build_json(df, out, args.generado)

    logger.success("Artefactos web de Dengue en {}", out)
    logger.info(
        "última semana: {} | casos nacionales esa semana: {:,} | entidades: {}",
        data["meta"]["ultima_semana"],
        data["meta"]["casos_semana_nacional"],
        len(data["cuadro_ultima_semana"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
