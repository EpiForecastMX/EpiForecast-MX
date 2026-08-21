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

# TAMANO FISICO FINAL. Springer exige >=6 pt de letra DENTRO de la figura
# (instructivo, 4.5). Generarla grande y dejar que LaTeX la reduzca divide el
# tamano por la escala: a 0.34 una etiqueta de 7.5 pt acaba en 2.5 pt. Por eso
# cada figura se genera al ancho exacto al que se imprime, con escala 1.
ANCHO_TEXTO_PT = 347.0
PULGADA = 72.0


def medida(frac: float, aspecto: float) -> tuple[float, float]:
    """(ancho, alto) en pulgadas para imprimirse a `frac` del bloque de texto."""
    w = ANCHO_TEXTO_PT * frac / PULGADA
    return w, w * aspecto


C_OBS, C_PROPHET, C_DEEPAR = "#4A4A4A", "#004D40", "#880E4F"
C_ENSEMBLE, C_STACK, C_GOLD, C_GREEN = "#FF6F00", "#1A237E", "#B8860B", "#0A4F3C"
plt.rcParams.update(
    {
        "font.size": 7,  # >= 6 pt de Springer, con margen
        "axes.titlesize": 7.5,
        "axes.labelsize": 6.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "pdf.fonttype": 42,  # TrueType incrustada: nada de Type 3
        "ps.fonttype": 42,
    }
)


def lunes(anio: int, semana: int) -> dt.date:
    """Lunes de la semana epidemiologica. El calendario de SINAVE puede llegar a la
    semana 53 en anios que ISO cierra en 52; en ese caso se extiende una semana."""
    try:
        return dt.date.fromisocalendar(anio, semana, 1)
    except ValueError:
        return dt.date.fromisocalendar(anio, 52, 1) + dt.timedelta(weeks=semana - 52)


def figura1() -> None:
    """Distribucion temporal: (a) casos anuales, (b) serie semanal nacional.

    Se regenera desde el paquete sellado y al ancho final. La version anterior
    rotulaba los trece valores anuales dentro de las barras; a esta escala esas
    etiquetas quedaban por debajo del minimo de Springer y el eje ya los comunica.
    """
    b = bundle.observado()
    b = b[b.Padecimiento == "Depresión"]
    anual = b.groupby("Anio")["Casos_semana"].sum().sort_index()
    sem = b.groupby(["Anio", "Semana"])["Casos_semana"].sum().sort_index()
    fechas = [lunes(int(a), int(w)) for a, w in sem.index]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=medida(0.80, 0.341))
    ax1.bar([str(a) for a in anual.index], anual.to_numpy(float) / 1000, color=C_GREEN, alpha=0.85)
    ax1.set_title("(a) Annual reported cases")
    ax1.set_ylabel("Thousands of cases")
    ax1.tick_params(axis="x", rotation=90)
    ax1.grid(axis="y", alpha=0.25, lw=0.4)
    ax1.set_axisbelow(True)

    ax2.axvspan(
        dt.date(2020, 3, 1),
        dt.date(2021, 12, 31),
        color=C_GOLD,
        alpha=0.15,
        label="COVID-19 disruption",
    )
    ax2.plot(fechas, sem.to_numpy(float), color=C_OBS, lw=0.6)
    ax2.set_title("(b) Weekly national series")
    ax2.set_ylabel("Cases per week")
    ax2.set_ylim(bottom=0)
    # a este ancho los años consecutivos se tocaban: uno de cada tres basta
    ax2.set_xticks([dt.date(a, 1, 1) for a in range(2014, 2027, 3)])
    ax2.set_xticklabels([str(a) for a in range(2014, 2027, 3)])
    ax2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, borderaxespad=0)
    ax2.grid(alpha=0.25, lw=0.4)
    fig.tight_layout()
    fig.savefig(SALIDA / "fig01_temporal_distribution.pdf")
    plt.close(fig)
    print(
        f"  Figura 1  {anual.index.min()}-{anual.index.max()}  "
        f"{len(sem)} semanas  ultimo anio {anual.iloc[-1]:,.0f}"
    )


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
        2, 1, figsize=medida(0.86, 0.605), gridspec_kw={"height_ratios": [2.0, 1.0]}
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
    # Los titulos internos repetian el pie de figura y a este ancho se recortaban.
    # Basta un rotulo de panel; el pie explica el contenido.
    ax1.set_title("(a)", loc="left", fontweight="bold")
    ax1.set_ylabel("National cases per week")
    ax1.set_ylim(bottom=0)
    ax1.legend(fontsize=7.5, loc="lower right", frameon=False, ncol=2)
    ax1.grid(True, alpha=0.25, lw=0.5)

    dev = 100.0 * (f - y) / y
    etiquetas = [f"W{w:02d}" for w in sem]
    colores = [C_GREEN if abs(d) <= 5 else (C_ENSEMBLE if abs(d) <= 10 else C_DEEPAR) for d in dev]
    ax2.axhspan(-5, 5, color=C_GOLD, alpha=0.12, label="Planning tolerance ±5%")
    ax2.bar(etiquetas, dev, color=colores, width=0.66)
    for i, d in enumerate(dev):
        if abs(d) <= 5:  # dentro de la tolerancia: la banda ya lo comunica
            continue
        salto = 1.2 + (2.6 if i % 2 else 0)  # vecinas a distinta altura
        ax2.text(
            i,
            d + (salto if d >= 0 else -salto),
            f"{d:+.0f}",
            ha="center",
            va="bottom" if d >= 0 else "top",
            fontsize=6.5,
        )
    ax2.axhline(0, color="#333", lw=0.8)
    # holgura arriba y abajo: sin ella la etiqueta de la peor semana choca con el titulo
    # holgura suficiente para que las etiquetas de las barras extremas no se corten
    margen = max(abs(dev).max() * 0.28, 8)
    ax2.set_ylim(dev.min() - margen, dev.max() + margen)
    ax2.set_ylabel("Deviation (%)")
    ax2.set_title("(b)", loc="left", fontweight="bold")
    ax2.legend(loc="upper right", frameon=False, bbox_to_anchor=(1.0, 1.32), borderaxespad=0)
    ax2.grid(True, axis="y", alpha=0.25, lw=0.5)
    # a este ancho las 17 etiquetas se tocaban: se rotulan las impares y se rotan
    for i, lab in enumerate(ax2.get_xticklabels()):
        lab.set_rotation(90)
        if i % 2:
            lab.set_visible(False)
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
    fig, ax = plt.subplots(figsize=medida(0.95, 0.439))
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
    # La anotacion de la mediana de CV se retiro: caia sobre los bigotes de las
    # cajas y el pie de figura ya dice que representa la linea discontinua.
    ax.set_xticks(range(len(estratos)))
    ax.set_xticklabels([s[1] for s in estratos])
    ax.set_ylabel("Out-of-sample 2026 sMAPE (%)")
    ax.set_xlabel("Demographic stratum")
    # la ventana del rotulo se DERIVA del dato: si cambia, cambia con el, y no puede
    # contradecir al pie de figura ni al JSON
    # el titulo interno duplicaba el pie y se recortaba a este ancho
    ax.set_ylim(0, float(np.ceil(tope / 5) * 5))
    ax.legend(
        handles=[
            mpatches.Patch(facecolor=c, alpha=0.55, hatch=h, label=lab) for _, lab, c, h in modelos
        ],
        ncol=4,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
        columnspacing=1.2,
        handlelength=1.4,
    )
    ax.grid(True, axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig(SALIDA / "fig20_oos_perstate.pdf")
    plt.close(fig)
    med = {m: round(float(oos[f"oos_{m}"].median()), 2) for m, *_ in modelos}
    print(f"  Figura 4  n={len(oos)}  medianas {med}")


if __name__ == "__main__":
    print("FASE 4 · FIGURAS —", bundle.sello())
    figura1()
    figura3()
    figura4()
    print(f"  escritas en {SALIDA}")
