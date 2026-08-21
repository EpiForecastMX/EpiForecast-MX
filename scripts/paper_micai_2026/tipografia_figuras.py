#!/usr/bin/env python3
"""Gate: ninguna letra dentro de una figura por debajo del minimo de Springer.

«The lettering in figures should not use font sizes smaller than 6 pt (~2 mm
character height)» -- instructivo de autores, seccion 4.5.

Ningun gate anterior lo veia: la figura se genera grande y LaTeX la reduce al
incluirla, asi que el tamano nominal del generador no dice nada. Aqui se mide el
tamano EFECTIVO: el de la fuente dentro del PDF de la figura, multiplicado por la
escala con la que el .tex la imprime.

Uso:  .venv/bin/python scripts/paper_micai_2026/tipografia_figuras.py
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import zlib

RAIZ = Path(__file__).resolve().parents[2]
MICAI = RAIZ / "Congresos/MICAI"
TEX = MICAI / "paper_camera_ready.tex"
MINIMO = 6.0
ANCHO_TEXTO = 347.0  # pt, bloque de texto de llncs


def escalas() -> dict[str, float]:
    """Factor de reduccion con el que el .tex imprime cada figura."""
    t = TEX.read_text()
    out = {}
    for frac, fig in re.findall(r"\\includegraphics\[width=([0-9.]+)\\textwidth\]\{([^}]+)\}", t):
        info = subprocess.run(
            ["pdfinfo", str(MICAI / "Figures" / fig)], capture_output=True, text=True, check=False
        ).stdout
        m = re.search(r"Page size:\s+([0-9.]+)", info)
        if m:
            out[fig] = ANCHO_TEXTO * float(frac) / float(m.group(1))
    return out


def tamanos(pdf: Path) -> list[float]:
    """Tamanos de fuente presentes en el PDF, en puntos nativos."""
    datos = pdf.read_bytes()
    flujos = []
    for m in re.finditer(rb"stream\r?\n", datos):
        fin = datos.find(b"endstream", m.end())
        if fin < 0:
            continue
        try:
            flujos.append(zlib.decompress(datos[m.end() : fin]).decode("latin-1"))
        except Exception:  # noqa: BLE001 - flujos no comprimidos o binarios
            continue
    vistos = []
    for f in flujos:
        # "/F1 9.5 Tf" fija la fuente; el Tm que lo rodea puede reescalar
        for tf in re.finditer(r"/[A-Za-z0-9]+\s+([0-9.]+)\s+Tf", f):
            vistos.append(float(tf.group(1)))
    return vistos


def revisa() -> list[tuple[str, float, float, float]]:
    filas = []
    for fig, esc in sorted(escalas().items()):
        t = tamanos(MICAI / "Figures" / fig)
        if not t:
            filas.append((fig, esc, float("nan"), float("nan")))
            continue
        filas.append((fig, esc, min(t), min(t) * esc))
    return filas


if __name__ == "__main__":
    print("=" * 74)
    print(f"TIPOGRAFIA EN FIGURAS — minimo de Springer: {MINIMO} pt")
    print("=" * 74)
    print(f"\n  {'figura':<36}{'escala':>8}{'nativo':>9}{'efectivo':>10}")
    malas = []
    for fig, esc, nat, ef in revisa():
        marca = "" if ef >= MINIMO else "  <-- POR DEBAJO"
        if ef < MINIMO:
            malas.append((fig, ef))
        print(f"  {fig:<36}{esc:>8.3f}{nat:>8.1f}pt{ef:>9.2f}pt{marca}")
    print("\n  VEREDICTO:", "FALLA" if malas else "PASA")
    sys.exit(1 if malas else 0)
