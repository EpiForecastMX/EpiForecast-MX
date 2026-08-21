#!/usr/bin/env python3
"""Gate: ninguna letra dentro de una figura por debajo del minimo de Springer.

«The lettering in figures should not use font sizes smaller than 6 pt (~2 mm
character height)» -- instructivo de autores, seccion 4.5.

Se mide sobre el PDF ENSAMBLADO, no sobre los archivos de figura sueltos. Dos
razones, ambas aprendidas a golpes:

  - la version anterior solo miraba lo que entra por \\includegraphics, asi que el
    diagrama TikZ de la Figura 2 le era invisible y el gate daba verde en falso;
  - leia el tamano nominal del operador Tf e ignoraba el escalado por matriz de
    texto, de modo que tampoco median bien las que si veia.

El texto rotado necesita otra lectura: para un glifo girado, `size` devuelve la
extension de la tinta, no el cuerpo de la fuente; el cuerpo esta en `width`.

Region de figura: en este paper las cuatro son flotantes [t]/[!h] que ocupan la
parte alta de su pagina, asi que se considera figura todo lo que esta por encima
del pie «Fig. N.».

Uso:  .venv/bin/python scripts/paper_micai_2026/tipografia_figuras.py
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

import pdfplumber

RAIZ = Path(__file__).resolve().parents[2]
PDF = RAIZ / "Congresos/MICAI/paper_camera_ready.pdf"
MINIMO = 6.0
CAPTION_PT = 9.0  # LNCS compone los pies a 9 pt
MARGEN_PT = 134.8  # margen izquierdo del bloque de texto, en coordenadas del PDF
ESPERADAS = [1, 2, 3, 4]


def _efectivo(c: dict) -> float:
    """Cuerpo de la fuente del glifo, tenga o no rotacion."""
    return float(c["width"]) if not c["upright"] else float(c["size"])


def revisa() -> list[tuple[int, str, float, int]]:
    """(pagina, figura, minimo efectivo, glifos por debajo) por cada figura hallada."""
    filas = []
    with pdfplumber.open(PDF) as doc:
        for n, pagina in enumerate(doc.pages, start=1):
            chars = pagina.chars
            texto = "".join(c["text"] for c in chars)
            # Un pie de figura no es cualquier «Fig. N»: LNCS los compone a 9 pt y
            # arrancando en el margen izquierdo del bloque de texto. Las menciones
            # dentro del parrafo van a 10 pt y en cualquier x, y antes se colaban
            # como si fueran figuras.
            m = None
            for cand in re.finditer(r"Fig\.\s*(\d+)", texto):
                c = chars[cand.start()]
                if abs(c["size"] - CAPTION_PT) < 0.3 and abs(c["x0"] - MARGEN_PT) < 2:
                    m = cand
                    break
            if not m:
                continue
            tope = chars[m.start()]["top"]
            dentro = [c for c in chars if c["top"] < tope - 1]
            if not dentro:
                continue
            tam = [_efectivo(c) for c in dentro]
            bajos = sum(1 for t in tam if t < MINIMO)
            filas.append((n, f"Fig. {m.group(1)}", min(tam), bajos))
    return filas


if __name__ == "__main__":
    print("=" * 72)
    print(f"TIPOGRAFIA EN FIGURAS — minimo de Springer: {MINIMO} pt")
    print("  medido sobre el PDF ensamblado, incluidas las figuras TikZ")
    print("=" * 72)
    filas = revisa()
    print(f"\n  {'pagina':<9}{'figura':<10}{'minimo':>10}{'glifos <6pt':>14}")
    malas = []
    for pg, fig, mn, bajos in filas:
        marca = "" if bajos == 0 else "  <-- INCUMPLE"
        if bajos:
            malas.append((fig, mn, bajos))
        print(f"  {pg:<9}{fig:<10}{mn:>8.2f}pt{bajos:>14}{marca}")
    halladas = [int(f.split()[1].rstrip(".")) for _, f, _, _ in filas]
    if halladas != ESPERADAS:
        print(f"\n  FIGURAS DETECTADAS {halladas}, se esperaban {ESPERADAS}:")
        print("  el gate no esta midiendo lo que cree medir")
        sys.exit(1)
    print("\n  VEREDICTO:", "FALLA" if malas else "PASA")
    sys.exit(1 if malas else 0)
