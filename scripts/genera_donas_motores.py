#!/usr/bin/env python
"""genera_donas_motores.py — Donas de distribución de motores productivos por padecimiento neuro.

Genera ``{padecimiento}_motores_dona.png`` (Depresión, Parkinson, Alzheimer) para el EpiBot,
con el mismo estilo que la dona de Dengue. Fuente: tabla de producción de 333 modelos.

Uso:
    python scripts/genera_donas_motores.py --out ../EpiForecast-IMSS-Dashboard/Reports/motores
"""

from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

from epiforecast.utils.config import conf, logger  # noqa: E402
from epiforecast.visualization.web_theme import BG, DPI, GRID, MUTED, TEXT  # noqa: E402

# Color de marca por motor (consistente con la dona de Dengue).
MOTOR_COLOR = {
    "DeepAR": "#F472B6",
    "Prophet": "#2DD4BF",
    "Ensemble": "#FF8A4C",
    "Stacking": "#8B7FE8",
    "NBGLM": "#F59E0B",
}
NEURO = ["Depresion", "Parkinson", "Alzheimer"]


def _dona(pad: str, dist: dict[str, int], out: Path) -> None:
    items = sorted(dist.items(), key=lambda kv: -kv[1])
    labels = [m for m, _ in items]
    vals = [int(v) for _, v in items]
    colors = [MOTOR_COLOR.get(m, "#7E8BA6") for m in labels]
    total = sum(vals)
    if not total:
        return

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    wedges, _ = ax.pie(
        vals,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": BG, "linewidth": 2.5},
    )
    ax.text(
        0, 0.10, str(total), ha="center", va="center", color=TEXT, fontsize=30, fontweight="bold"
    )
    ax.text(0, -0.18, "series", ha="center", va="center", color=MUTED, fontsize=11)
    leyenda = [f"{m}  ·  {v} ({v / total * 100:.0f}%)" for m, v in zip(labels, vals, strict=False)]
    ax.legend(
        wedges,
        leyenda,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        facecolor=BG,
        edgecolor=GRID,
        labelcolor=TEXT,
        fontsize=11.5,
        handlelength=1.1,
    )
    ax.set_title(
        f"Motores productivos de {pad} (por serie)",
        color=TEXT,
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    fig.savefig(
        out / f"{pad.lower()}_motores_dona.png", facecolor=BG, bbox_inches="tight", pad_inches=0.2
    )
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/motores)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tabla = Path(conf["paths"]["reports"]) / "ProdDetails" / "tabla_333_modelos_produccion.xlsx"
    t = pd.read_excel(tabla, usecols=["padecimiento", "modelo_produccion"])
    n = 0
    for pad in NEURO:
        dist = t[t["padecimiento"] == pad]["modelo_produccion"].value_counts().to_dict()
        if dist:
            _dona(pad, {str(k): int(v) for k, v in dist.items()}, out)
            n += 1
    logger.success("Donas de motores neuro: {} generadas en {}", n, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
