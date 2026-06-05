#!/usr/bin/env python
"""dengue_pronostico_nino.py — Pronóstico de dengue al ritmo de El Niño (gráfica lineal).

Genera ``dengue_pronostico_nino.png``: serie nacional semanal 2014-2026 (real) + pronóstico
NB-GLM condicionado al PRÓXIMO El Niño, en escala lineal (año en X, casos por semana en Y),
con los periodos de El Niño (cálido) y La Niña (frío) sombreados desde 2014.

El dengue en México sigue al ciclo ENSO (brotes 2014, 2019, 2024 en años de El Niño). En vez de
extrapolar una estacionalidad plana, proyectamos un escenario climatológico de ENSO (el próximo
El Niño moderado hacia 2027-2028, ciclo ~4 años) y se lo damos al regresor de El Niño del NB-GLM:
así el modelo anticipa el próximo gran brote alineado con ese El Niño. La MAGNITUD exacta es
incierta (ENSO no se pronostica a años); es un escenario de planeación, no una certeza.

Uso:
    python scripts/dengue_pronostico_nino.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
from matplotlib.patches import Patch  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

from epiforecast.data import enso  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.models.nbglm.model import NBGLMForecaster  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402
from epiforecast.visualization.web_theme import (  # noqa: E402
    BG,
    DPI,
    GRID,
    MINT,
    MUTED,
    PINK,
    TEXT,
)

A9091 = Path(conf["paths"]["interim"]) / "dengue_a90a91_nacional.csv"
WARM, COLD, FC = "#E8553A", MINT, "#5B8DEF"  # El Niño / La Niña / pronóstico
HORIZON_WEEKS = 235  # ~4.5 años: cubre el próximo ciclo completo (brote ~2029 + años bajos)
# Escenario ENSO futuro. El ciclo epidémico del dengue es de ~5 años (brotes 2014, 2019, 2024),
# así que el PRÓXIMO gran brote se espera hacia 2029 (2024 + 5), con El Niño desarrollándose en
# 2028-2029. Periodo 5 años, pico ONI ~2028.9 (fin de 2028, ~16 sem antes del brote dengue).
_ENSO_AMP, _ENSO_CENTER, _ENSO_PEAK, _ENSO_PERIOD = 1.4, 0.0, 2029.0, 5.0
_BROTE_ANIO = 2029
# Ancla la tendencia a una semana previa a la epidemia de 2024: baja el piso para que los años
# SIN El Niño queden bajos (~1.2k/sem, como 2025) y solo el clima eleve el brote (2029 ~4k/sem).
_TREND_ANCHOR = 180


def _yf(t: pd.Timestamp) -> float:
    t = pd.Timestamp(t)
    return t.year + (t.dayofyear - 1) / 365.0


def _serie_modelado() -> pd.DataFrame:
    df = cargar_boletin_dengue()
    g = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g = g.sort_values(["Anio", "Semana"])
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    s = g.rename(columns={"Casos_semana": "y"})[["ds", "y"]]
    return s.groupby("ds", as_index=False)["y"].sum().sort_values("ds").reset_index(drop=True)


def _serie_contexto() -> pd.DataFrame:
    if not A9091.exists():
        return pd.DataFrame(columns=["ds", "y"])
    old = pd.read_csv(A9091).sort_values(["Anio", "Semana"])
    old["y"] = (
        old.groupby("Anio")["confirmado_acum_nacional"]
        .diff()
        .fillna(old["confirmado_acum_nacional"])
        .clip(lower=0)
    )
    old["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(old["Anio"], old["Semana"], strict=False)
    ]
    return old[["ds", "y"]].reset_index(drop=True)


def _escenario_oni(last: pd.Timestamp, fut_ds: pd.DatetimeIndex) -> tuple[pd.Series, np.ndarray]:
    """ONI observado + próximo El Niño climatológico. Devuelve (serie completa, regresor rezagado)."""
    obs = enso.load_oni_weekly()
    obs = obs[obs["ds"] <= last]
    cos = np.array(
        [
            _ENSO_CENTER + _ENSO_AMP * np.cos(2 * np.pi * (_yf(t) - _ENSO_PEAK) / _ENSO_PERIOD)
            for t in fut_ds
        ]
    )
    o0 = float(obs["oni"].iloc[-1])
    for i in range(min(26, len(cos))):  # transición suave desde el último ONI observado
        w = i / 26
        cos[i] = (1 - w) * o0 + w * cos[i]
    full = (
        pd.concat([obs[["ds", "oni"]], pd.DataFrame({"ds": fut_ds, "oni": cos})])
        .drop_duplicates("ds")
        .set_index("ds")["oni"]
        .sort_index()
    )
    lag = pd.Timedelta(weeks=16)
    reg = np.array(
        [full.reindex(full.index.union([t - lag])).interpolate().loc[t - lag] for t in fut_ds]
    )
    return full, reg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    serie, ctx = _serie_modelado(), _serie_contexto()
    last = serie["ds"].max()
    fut_ds = pd.date_range(last + pd.Timedelta(weeks=1), periods=HORIZON_WEEKS, freq="W-MON")
    oni_full, oni_reg = _escenario_oni(last, fut_ds)

    model = NBGLMForecaster(padecimiento="Dengue")
    model.fit(serie[["ds", "y"]])
    fc = model.predict(horizon=HORIZON_WEEKS, future_oni=oni_reg, trend_anchor_weeks=_TREND_ANCHOR)
    fut = fc[fc["ds"] > last].copy()

    ymax = max(float(serie["y"].max()), float(fut["yhat"].max())) * 1.1

    fig, ax = plt.subplots(figsize=(13, 5.6), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # Sombreado ENSO SUAVE: opacidad proporcional a la intensidad del ONI (sin bordes duros);
    # el color se desvanece al acercarse al umbral, dando bandas difuminadas en vez de líneas.
    ox = oni_full.reset_index()
    ox["x"] = ox["ds"].map(_yf)
    xs, ov = ox["x"].to_numpy(), ox["oni"].to_numpy()
    dx = float(xs[1] - xs[0]) if len(xs) > 1 else 0.02
    for xi, oi in zip(xs, ov, strict=False):
        if oi > 0.5:
            ax.axvspan(
                xi - dx / 2,
                xi + dx / 2,
                color=WARM,
                alpha=min((oi - 0.5) / 1.5, 1.0) * 0.16,
                zorder=0,
                linewidth=0,
            )
        elif oi < -0.5:
            ax.axvspan(
                xi - dx / 2,
                xi + dx / 2,
                color=COLD,
                alpha=min((-oi - 0.5) / 1.5, 1.0) * 0.14,
                zorder=0,
                linewidth=0,
            )

    # Líneas: contexto (2014-2018), histórico (2018-2026), pronóstico.
    if not ctx.empty:
        ax.plot(ctx["ds"].map(_yf), ctx["y"], color=MUTED, linewidth=0.9, alpha=0.65, zorder=2)
    ax.plot(serie["ds"].map(_yf), serie["y"], color=TEXT, linewidth=1.3, zorder=3)
    ax.plot(
        fut["ds"].map(_yf),
        fut["yhat"],
        color=FC,
        linewidth=2.0,
        linestyle="--",
        zorder=4,
    )
    ax.axvline(_yf(last), color=MUTED, linewidth=0.8, linestyle=":", alpha=0.7, zorder=2)

    # Anotaciones de los brotes (en años de El Niño) y del próximo.
    for yr, txt in [(2014, "Brote 2014"), (2019, "Brote 2019"), (2024, "Brote 2024")]:
        seg = serie[serie["ds"].dt.year == yr] if yr >= 2018 else ctx[ctx["ds"].dt.year == yr]
        if not seg.empty:
            pk = seg.loc[seg["y"].idxmax()]
            ax.annotate(
                txt,
                xy=(_yf(pk["ds"]), pk["y"]),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                color=PINK,
                fontsize=8,
                fontweight="bold",
                zorder=5,
            )
    pk_f = fut.loc[fut["yhat"].idxmax()]
    ax.annotate(
        f"Próximo brote esperado\n(El Niño ~{_BROTE_ANIO})",
        xy=(_yf(pk_f["ds"]), pk_f["yhat"]),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        color=FC,
        fontsize=8.5,
        fontweight="bold",
        zorder=5,
    )

    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6, alpha=0.45, zorder=0)
    ax.set_xlim(2014, _yf(fut_ds[-1]))
    ax.set_ylim(0, ymax)
    ax.set_xlabel("Año", color=MUTED, fontsize=10)
    ax.set_ylabel("Casos confirmados por semana", color=MUTED, fontsize=10)
    ax.set_title(
        "Pronóstico de dengue al ritmo de El Niño: el próximo gran brote llega con el próximo El Niño",
        color=TEXT,
        fontsize=12.5,
        pad=40,  # deja sitio a la leyenda, que va FUERA del área de datos (arriba)
        fontweight="bold",
    )
    handles = [
        plt.Line2D([], [], color=TEXT, lw=1.4, label="Histórico real (2018-2026)"),
        plt.Line2D([], [], color=MUTED, lw=1.0, alpha=0.7, label="Contexto 2014-2018 (A90/A91)"),
        plt.Line2D([], [], color=FC, lw=2.0, ls="--", label="Pronóstico NB-GLM (próximo El Niño)"),
        Patch(facecolor=WARM, alpha=0.5, label="El Niño (ONI > +0.5 °C)"),
        Patch(facecolor=COLD, alpha=0.5, label="La Niña (ONI < -0.5 °C)"),
    ]
    ax.legend(
        handles=handles,
        facecolor=BG,
        edgecolor=GRID,
        labelcolor=TEXT,
        fontsize=8.3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.005),  # arriba del eje, sin encimar los datos
        ncol=5,
        columnspacing=1.3,
        handlelength=1.6,
        frameon=False,
    )
    fig.text(
        0.5,
        0.005,
        "Los grandes brotes ocurren cada ~5 años en años de El Niño (2014, 2019, 2024). Por eso el "
        "próximo se espera hacia 2029: el pronóstico proyecta el siguiente El Niño (2028-2029) y lo "
        "alimenta al modelo NB-GLM, con años bajos en medio. La magnitud exacta es incierta (ENSO no "
        "se pronostica a años); es un escenario de planeación, no una certeza.",
        ha="center",
        va="bottom",
        color=MUTED,
        fontsize=8,
        wrap=True,
    )
    fig.subplots_adjust(top=0.82, bottom=0.14, left=0.06, right=0.98)
    fig.savefig(
        out / "dengue_pronostico_nino.png", facecolor=BG, bbox_inches="tight", pad_inches=0.2
    )
    plt.close(fig)
    logger.success(
        "Pronóstico El Niño: brote {} ~{:,.0f} casos/sem | -> {}",
        int(pk_f["ds"].year),
        pk_f["yhat"],
        out / "dengue_pronostico_nino.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
