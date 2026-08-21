#!/usr/bin/env python3
"""Gate: la ventana por serie tiene que decir lo mismo en los cuatro sitios.

El analisis por serie corre sobre una ventana distinta a la del agregado nacional
—no todas las series tienen pronostico en la primera semana— y esa diferencia ya
se contradijo una vez: el rotulo dentro de la Figura 4 decia una ventana y su pie
decia otra. Aqui la ventana se toma del JSON, que la deriva de los datos, y se
exige que coincida en el .tex, en los pies de figura y tabla, y en el PDF de la
propia figura.

Uso:  .venv/bin/python scripts/paper_micai_2026/ventanas_coherentes.py
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

RAIZ = Path(__file__).resolve().parents[2]
JSON = RAIZ / "reports/paper_micai_2026/fase4_cifras.json"
TEX = RAIZ / "Congresos/MICAI/paper_camera_ready.tex"
FIG4 = RAIZ / "Congresos/MICAI/Figures/fig20_oos_perstate.pdf"


def _norma(s: str) -> str:
    """Unifica guiones: LaTeX escribe --, matplotlib un en-dash, el PDF otro."""
    return re.sub(r"[-–—]+", "-", s.replace("--", "-"))


def revisa() -> list[str]:
    d = json.loads(JSON.read_text())
    serie = _norma(d["por_serie"]["ventana"])  # p. ej. W03-W18
    nacional = _norma(d["corregida"]["ventana"])  # p. ej. W02-W18
    fallos = []

    if serie == nacional:
        fallos.append(
            f"las dos ventanas coinciden ({serie}); este gate asume que difieren, "
            "revisar si el supuesto sigue vigente"
        )

    tex = _norma("\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in TEX.read_text().splitlines()))

    # el pie de la Figura 4 y el de la tabla de ablacion hablan de la ventana por serie
    for etiqueta, ancla in [
        (
            "pie de la Figura 4",
            r"per-series symmetric error by model and\s+demographic stratum over (W\d+-W\d+)",
        ),
        ("pie de la ablacion", r"over the 99 directly observed series, (W\d+-W\d+)"),
    ]:
        m = re.search(ancla, tex)
        if not m:
            fallos.append(f"{etiqueta}: no se encontro la declaracion de ventana")
        elif m.group(1) != serie:
            fallos.append(f"{etiqueta}: dice {m.group(1)}, el dato es {serie}")

    # y el rotulo dentro del PDF de la figura
    if FIG4.exists():
        txt = _norma(
            subprocess.run(
                ["pdftotext", str(FIG4), "-"], capture_output=True, text=True, check=False
            ).stdout
        )
        if serie not in txt:
            hallados = set(re.findall(r"W\d+-W\d+", txt))
            fallos.append(
                f"rotulo de la Figura 4: no dice {serie} (encontrado: {hallados or 'nada'})"
            )

    # la ventana nacional no puede haber quedado escrita como la de series
    if re.search(r"Over the \d+ complete weeks " + re.escape(serie), tex):
        fallos.append(f"el agregado nacional declara {serie}; deberia declarar {nacional}")

    return fallos


if __name__ == "__main__":
    f = revisa()
    print("=" * 70)
    print("GATE DE VENTANAS")
    print("=" * 70)
    if not f:
        d = json.loads(JSON.read_text())
        print(
            f"  agregado nacional : {d['corregida']['ventana']} "
            f"({d['corregida']['n_semanas']} semanas)"
        )
        print(
            f"  por serie         : {d['por_serie']['ventana']} "
            f"({d['por_serie']['semanas_por_serie']} semanas)"
        )
        print("\n  Coherente en JSON, .tex, pies y figura.")
        raise SystemExit(0)
    for x in f:
        print(f"  FALLA: {x}")
    raise SystemExit(1)
