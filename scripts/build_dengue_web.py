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

# Paleta Clinical Indigo (alineada con el landing / EpiBot).
BG = "#131C30"
GRID = "#243150"
TEXT = "#E7ECF5"
MUTED = "#9DB0D0"
AMBER = "#F59E0B"  # acento Dengue
MINT = "#2DD4BF"
PINK = "#F472B6"

MESES_SEM = 52


def _style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)


def _fig(figsize: tuple[float, float]) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_facecolor(BG)
    _style_ax(ax)
    return fig, ax


def chart_nacional_semanal(df: pd.DataFrame, out: Path) -> None:
    """Serie de tiempo: casos confirmados de Dengue por semana, nacional."""
    g = df.groupby(["Anio", "Semana"], as_index=False).Casos_semana.sum()
    g["t"] = g.Anio + (g.Semana.astype(int) - 1) / MESES_SEM
    fig, ax = _fig((11, 4.2))
    ax.plot(g.t, g.Casos_semana, color=AMBER, linewidth=1.8)
    ax.fill_between(g.t, g.Casos_semana, color=AMBER, alpha=0.12)
    ax.set_title(
        "Incidencia semanal nacional de Dengue confirmado (2020-2026)", fontsize=12, pad=12
    )
    ax.set_ylabel("Casos por semana")
    ax.set_xlabel("Año epidemiológico")
    fig.tight_layout()
    fig.savefig(out / "dengue_nacional_semanal.png", facecolor=BG)
    plt.close(fig)


def chart_totales_anuales(df: pd.DataFrame, out: Path) -> None:
    """Barras: casos confirmados por año (resalta el pico epidémico 2024)."""
    g = df.groupby("Anio", as_index=False).Casos_semana.sum()
    colors = [AMBER if a == g.loc[g.Casos_semana.idxmax(), "Anio"] else MINT for a in g.Anio]
    fig, ax = _fig((9, 4.0))
    bars = ax.bar(g.Anio.astype(str), g.Casos_semana, color=colors, width=0.62)
    for b, v in zip(bars, g.Casos_semana, strict=True):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{int(v):,}",
            ha="center",
            va="bottom",
            color=TEXT,
            fontsize=8.5,
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
    fig, ax = _fig((11, 4.0))
    ax.plot(clim["wk"], clim["Casos_semana"], color=MINT, linewidth=2.0, marker="o", markersize=3)
    ax.fill_between(clim["wk"], clim["Casos_semana"], color=MINT, alpha=0.10)
    ax.set_title(
        "Estacionalidad del Dengue — promedio por semana epidemiológica (2020-2026)",
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
    mask = z > 3
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
    parser.add_argument("--csv", default="data/interim/dengue_boletin.csv")
    parser.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    parser.add_argument(
        "--generado", default="", help="Fecha de generación (ISO); vacío = no estampar"
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    chart_nacional_semanal(df, out)
    chart_totales_anuales(df, out)
    chart_estacionalidad(df, out)
    chart_outliers(df, out)
    data = build_json(df, out, args.generado)

    print(f"Artefactos en {out}")
    print(
        f"  última semana: {data['meta']['ultima_semana']} | "
        f"casos nacionales esa semana: {data['meta']['casos_semana_nacional']:,} | "
        f"entidades: {len(data['cuadro_ultima_semana'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
