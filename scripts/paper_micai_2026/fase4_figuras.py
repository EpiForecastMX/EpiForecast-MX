#!/usr/bin/env python3
"""Fase 4: regenerar las Figuras 3 y 4 desde el paquete sellado, con la alineacion
corregida. Mantiene el diseno y la paleta del generador original; lo que cambia es la
fuente (tableau sellado, no el knowledge.json del dashboard) y el cruce de semanas.

Uso:  .venv/bin/python scripts/paper_micai_2026/fase4_figuras.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bundle  # noqa: E402
import fase4_cifras as cifras  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "Congresos/MICAI/Figures"
RESULT = RAIZ / "reports/paper_micai_2026/resultados"

C_OBS, C_PROPHET, C_DEEPAR = "#4A4A4A", "#004D40", "#880E4F"
C_ENSEMBLE, C_STACK, C_GOLD, C_GREEN = "#FF6F00", "#1A237E", "#B8860B", "#0A4F3C"
plt.rcParams.update({"font.size": 9.5, "axes.titlesize": 11})


def lunes(anio: int, semana: int) -> dt.date:
    """Lunes de la semana epidemiologica. El calendario de SINAVE puede llegar a la
    semana 53 en anios que ISO cierra en 52; en ese caso se extiende una semana."""
    try:
        return dt.date.fromisocalendar(anio, semana, 1)
    except ValueError:
        return dt.date.fromisocalendar(anio, 52, 1) + dt.timedelta(weeks=semana - 52)


def figura3() -> None:
    """Validacion prospectiva nacional: observado vs pronostico bloqueado, W02-W18."""
    obs = cifras.observado_nacional()["general"]
    pron = cifras.pronostico_nacional(1)["general"]["ensemble"]
    sem = [w for w in cifras.VENTANA if w in obs.index and w in pron.index]
    y = obs.reindex(sem).to_numpy(float)
    f = pron.reindex(sem).to_numpy(float)
    fechas = [lunes(2026, w) for w in sem]

    b = bundle.observado()
    b = b[(b.Padecimiento == "Depresión") & (b.Anio == 2025)]
    ctx = b.groupby("Semana")["Casos_semana"].sum().sort_index()
    ctx = ctx[ctx.index >= 40]
    ctx_f = [lunes(2025, int(w)) for w in ctx.index]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12.23, 7.4), gridspec_kw={"height_ratios": [2.0, 1.0]}
    )
    ax1.plot(
        ctx_f,
        ctx.to_numpy(float),
        color=C_OBS,
        lw=1.6,
        marker="o",
        ms=3,
        label="Observed (SINAVE bulletin)",
    )
    ax1.plot(fechas, y, color=C_OBS, lw=1.9, marker="o", ms=4)
    ax1.plot(
        fechas,
        f,
        color=C_GREEN,
        lw=1.9,
        ls=(0, (5, 2)),
        marker="s",
        ms=3.5,
        label="Locked Ensemble forecast",
    )
    ax1.axvline(fechas[0], color="#999", lw=0.9, ls=":")
    ax1.set_title(
        "Depression: 2026 prospective evaluation — national general stratum, "
        "W02–W18 (every SINAVE bulletin since training cut-off)"
    )
    ax1.set_ylabel("National cases per week")
    ax1.set_ylim(bottom=0)
    ax1.legend(fontsize=8.5, loc="lower right", frameon=False, ncol=2)
    ax1.grid(True, alpha=0.25, lw=0.5)

    dev = 100.0 * (f - y) / y
    etiquetas = [f"W{w:02d}" for w in sem]
    colores = [C_GREEN if abs(d) <= 5 else (C_ENSEMBLE if abs(d) <= 10 else C_DEEPAR) for d in dev]
    ax2.axhspan(-5, 5, color=C_GOLD, alpha=0.12, label="Planning tolerance ±5%")
    ax2.bar(etiquetas, dev, color=colores, width=0.66)
    for i, d in enumerate(dev):
        ax2.text(
            i,
            d + (1.2 if d >= 0 else -1.2),
            f"{d:+.0f}",
            ha="center",
            va="bottom" if d >= 0 else "top",
            fontsize=7.5,
        )
    ax2.axhline(0, color="#333", lw=0.8)
    # holgura arriba y abajo: sin ella la etiqueta de la peor semana choca con el titulo
    ax2.set_ylim(min(dev.min() - 5, -8), max(dev.max() + 6, 10))
    ax2.set_ylabel("Deviation (%)")
    ax2.set_title(
        "Per-week deviation, locked forecast vs. SINAVE bulletin (W02–W18)", fontsize=10.5
    )
    ax2.legend(fontsize=8.5, loc="upper right", frameon=False)
    ax2.grid(True, axis="y", alpha=0.25, lw=0.5)
    plt.setp(ax2.get_xticklabels(), fontsize=8.5)
    fig.tight_layout()
    fig.savefig(SALIDA / "fig19_validation_2026.pdf")
    plt.close(fig)
    print(
        f"  Figura 3  W{sem[0]:02d}-W{sem[-1]:02d}  sMAPE {cifras.smape(y, f):.2f}%  "
        f"peor {dev[int(np.argmax(abs(dev)))]:+.1f}%"
    )


def figura4() -> None:
    """sMAPE fuera de muestra por serie, modelo y estrato (n=99)."""
    oos = pd.read_csv(RESULT / "oos_por_serie.csv")
    oos = oos[~oos.entidad.astype(str).str.startswith("Region ")]
    estratos = [("general", "General"), ("mujeres", "Women"), ("hombres", "Men")]
    modelos = [
        ("prophet", "Prophet", C_PROPHET, ""),
        ("deepar", "DeepAR", C_DEEPAR, "///"),
        ("ensemble", "Ensemble", C_ENSEMBLE, "..."),
        ("stacking", "Stacking", C_STACK, "xx"),
    ]
    fig, ax = plt.subplots(figsize=(9.5, 4.17))
    w = 0.19
    tope = 0.0
    for gi, (sx, _) in enumerate(estratos):
        d = oos[oos.modo == sx]
        for mi, (mk, _, col, hat) in enumerate(modelos):
            vals = d[f"oos_{mk}"].dropna().to_numpy(float)
            tope = max(
                tope,
                np.percentile(vals, 75)
                + 1.5 * (np.percentile(vals, 75) - np.percentile(vals, 25)),
            )
            bp = ax.boxplot(
                [vals],
                positions=[gi + (mi - 1.5) * w],
                widths=w * 0.9,
                patch_artist=True,
                showfliers=False,
                medianprops=dict(color="black", lw=1.1),
                whiskerprops=dict(color=col, lw=0.9),
                capprops=dict(color=col, lw=0.9),
            )
            bp["boxes"][0].set(facecolor=col, alpha=0.55, edgecolor=col, hatch=hat, lw=1.0)
    ax.axhline(5.99, color=C_DEEPAR, ls=(0, (4, 2)), lw=1.2)
    ax.text(
        2.45,
        8.5,
        "DeepAR cross-validation median (5.99%)",
        fontsize=8,
        color=C_DEEPAR,
        ha="right",
        style="italic",
    )
    ax.set_xticks(range(len(estratos)))
    ax.set_xticklabels([s[1] for s in estratos])
    ax.set_ylabel("Out-of-sample 2026 sMAPE (%)")
    ax.set_xlabel("Demographic stratum")
    ax.set_title(
        "Out-of-sample 2026 per-series error by model and stratum, W02–W18 "
        "(each box: 32 entities + national)"
    )
    ax.set_ylim(0, float(np.ceil(tope / 5) * 5))
    ax.legend(
        handles=[
            mpatches.Patch(facecolor=c, alpha=0.55, hatch=h, label=lab) for _, lab, c, h in modelos
        ],
        ncol=4,
        fontsize=8.5,
        loc="upper left",
        frameon=False,
    )
    ax.grid(True, axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig(SALIDA / "fig20_oos_perstate.pdf")
    plt.close(fig)
    med = {m: round(float(oos[f"oos_{m}"].median()), 2) for m, *_ in modelos}
    print(f"  Figura 4  n={len(oos)}  medianas {med}")


if __name__ == "__main__":
    print("FASE 4 · FIGURAS —", bundle.sello())
    figura3()
    figura4()
    print(f"  escritas en {SALIDA}")
