#!/usr/bin/env python
"""build_dengue_gallery.py — Gráficos por entidad/sexo de Dengue para la galería pública.

Para cada serie (entidad × sexo) genera un PNG con la realidad del boletín (histórico)
y el pronóstico del MOTOR PRODUCTIVO seleccionado por `produccion_dengue.py`, en el tema
Clinical Indigo. Los escribe en la estructura que espera la galería del dashboard
(`Reports/dengue/{Entidad}/Dengue_{Entidad}_{sexo}.png`) y emite la lista de items JSON
para inyectar en `Reports/index.html`.

Uso:
    python scripts/build_dengue_gallery.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402
from epiforecast.visualization.web_theme import (  # noqa: E402
    AMBER,
    BG,
    GRID,
    MINT,
    MUTED,
    PINK,
    TEXT,
)

PROD = Path(conf["paths"]["reports"]) / "ProdDetails" / "produccion_dengue.csv"
FC_BASE = Path(conf["paths"]["reports"]) / "forecasts"
SEXOS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}
MOTOR_COLOR = {"DeepAR": PINK, "Prophet": MINT, "NBGLM": AMBER}


def _safe(s: str) -> str:
    return s.replace(" ", "_").replace("/", "_")


def _real_general(df: pd.DataFrame) -> pd.DataFrame:
    """Serie real general (ds, y) = Casos_semana (la cantidad que modela el motor general)."""
    g = df.groupby(["Anio", "Semana"], as_index=False).agg(Casos_semana=("Casos_semana", "sum"))
    g = g.sort_values(["Anio", "Semana"])
    g["y"] = g["Casos_semana"]
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g[["ds", "y"]].reset_index(drop=True)


def _sex_prop(df: pd.DataFrame) -> tuple[float, float]:
    """Proporción (hombres, mujeres) de la entidad, del acumulado por sexo.

    El boletín reporta el total semanal (``Casos_semana``) y el acumulado por sexo en columnas
    distintas que NO reconcilian (sumar H+M del acumulado no da el total). Para que la galería sea
    consistente, hombres/mujeres se muestran como un REPARTO proporcional del total general por la
    razón de sexo observada: así H + M = general, exacto, en realidad y pronóstico.
    """
    g = df.groupby(["Anio", "Semana"], as_index=False).agg(
        ah=("Acumulado_hombres", "sum"), am=("Acumulado_mujeres", "sum")
    )
    g = g.sort_values(["Anio", "Semana"])
    h = float(g.groupby("Anio")["ah"].diff().fillna(g["ah"]).clip(lower=0).sum())
    m = float(g.groupby("Anio")["am"].diff().fillna(g["am"]).clip(lower=0).sum())
    tot = h + m
    return (0.5, 0.5) if tot <= 0 else (h / tot, m / tot)


def _forecast(motor: str, entidad: str, sexo: str, last_real: pd.Timestamp) -> pd.DataFrame:
    path = FC_BASE / motor.lower() / f"all_forecast_{motor.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    d = df[
        (df["meta_padecimiento"] == "Dengue")
        & (df["meta_entidad"].fillna("Nacional") == entidad)
        & (df["meta_modo"] == sexo)
    ].copy()
    d["ds"] = pd.to_datetime(d["ds"])
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in d.columns]
    return d[d["ds"] > last_real][cols].sort_values("ds").head(52)


def _chart(real: pd.DataFrame, fc: pd.DataFrame, motor: str, titulo: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=130)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    color = MOTOR_COLOR.get(motor, AMBER)
    ax.plot(real["ds"], real["y"], color=MUTED, linewidth=1.6, label="Real (boletín SINAVE)")
    if not fc.empty:
        if {"yhat_lower", "yhat_upper"} <= set(fc.columns):
            ax.fill_between(
                fc["ds"], fc["yhat_lower"].clip(lower=0), fc["yhat_upper"], color=color, alpha=0.15
            )
        ax.plot(
            fc["ds"],
            fc["yhat"].clip(lower=0),
            color=color,
            linewidth=2.2,
            label=f"Pronóstico ({motor})",
        )
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.4)
    ax.set_ylabel("Casos por semana", color=MUTED, fontsize=9)
    ax.set_title(titulo, color=TEXT, fontsize=12, pad=10, fontweight="bold")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    args = ap.parse_args()
    out_base = Path(args.out)

    prod = pd.read_csv(PROD)
    bol = cargar_boletin_dengue()
    bol["Entidad"] = bol["Entidad"].replace(ENTIDAD_DISPLAY)
    # Motor productivo de la serie GENERAL por entidad (hombres/mujeres se derivan del general).
    gen_motor = {
        str(row["entidad"]): str(row["motor_productivo"])
        for _, row in prod[prod["sexo"] == "general"].iterrows()
    }
    items = []
    n = 0
    for _, r in prod.iterrows():
        ent, sexo = str(r["entidad"]), str(r["sexo"])
        ent_disp = ENTIDAD_DISPLAY.get(ent, ent)
        sub = bol if ent == "Nacional" else bol[bol["Entidad"] == ent_disp]
        if sub.empty:
            continue
        # General real (Casos_semana) + su pronóstico; hombres/mujeres = general × proporción de
        # sexo, para que H + M = general (exacto) en realidad y pronóstico.
        motor = gen_motor.get(ent, str(r["motor_productivo"]))
        real = _real_general(sub)
        last_real = real["ds"].max()
        fc = _forecast(motor, ent, "general", last_real)
        if sexo != "general":
            p_h, p_m = _sex_prop(sub)
            p = p_h if sexo == "hombres" else p_m
            real = real.assign(y=real["y"] * p)
            fc = fc.copy()
            for c in ("yhat", "yhat_lower", "yhat_upper"):
                if c in fc.columns:
                    fc[c] = fc[c] * p
        safe_ent = _safe(ent_disp)
        # Carpeta en MINÚSCULA 'dengue/' (coincide con los assets de dengue.html ya
        # committeados; Netlify es case-sensitive, no usar 'Dengue/').
        rel = f"dengue/{safe_ent}/Dengue_{safe_ent}_{sexo}.png"
        titulo = f"Dengue — {ent_disp} ({SEXOS[sexo]})"
        _chart(real, fc, motor, titulo, out_base.parent / rel)
        items.append(
            {
                "p": "Dengue",
                "n": ent_disp,
                "c": "Nacional" if ent == "Nacional" else "Estatal",
                "s": SEXOS[sexo],
                "f": rel,
            }
        )
        n += 1
    (out_base / "_gallery_items.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    logger.success("Galería Dengue: {} gráficos en {} | items en _gallery_items.json", n, out_base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
