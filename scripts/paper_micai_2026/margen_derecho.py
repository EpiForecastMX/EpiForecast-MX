"""Gate: ninguna linea puede sacar tinta al margen derecho.

Nace de un fallo real. Una linea de la Discusion se salia 3.6 pt del bloque de
texto y nada la frenaba: el control de compilacion contaba los avisos "Overfull"
del .log y solo bloqueaba por encima de 15 pt. Ese umbral es una convencion
nuestra, no una tolerancia que Springer conceda, y a simple vista se veia.

Mide TINTA sobre el PDF ensamblado, no avisos del .log. Son cosas distintas: el
aviso habla de cuanto le sobra a la caja del renglon, y aqui interesa cuanto
sobresale de verdad del bloque, que es lo que ve quien lee.

Deja colgar la PUNTUACION. Una raya o un guion al final de linea que asoma unos
puntos es composicion normal --puntuacion colgante-- y no es un defecto; una
letra fuera del bloque si lo es. Por eso hay dos umbrales.

Uso:
    python scripts/paper_micai_2026/margen_derecho.py [ruta.pdf]
Devuelve 0 si nada sobresale de mas, 1 si algo lo hace.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pdfplumber

RAIZ = Path(__file__).resolve().parents[2]
PDF = RAIZ / "Congresos" / "MICAI" / "paper_camera_ready.pdf"

MARGEN_IZQ = 134.8  # borde izquierdo del bloque de texto en LNCS a4paper
ANCHO = 347.0  # \textwidth
DERECHA = MARGEN_IZQ + ANCHO

# Puntuacion que puede colgar, y cuanto. El resto no cuelga nada.
COLGABLE = set("—–-.,;:!?)]}”’")
TOLERANCIA_PUNTUACION = 4.0
TOLERANCIA_LETRA = 0.5


def _lineas(pagina) -> list[list[dict]]:
    agrupadas: dict[float, list[dict]] = {}
    for c in pagina.chars:
        agrupadas.setdefault(round(c["top"], 1), []).append(c)
    return [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(agrupadas.items())]


def revisa(ruta: Path) -> int:
    print("=" * 72)
    print(f"MARGEN DERECHO — tinta fuera del bloque (borde en {DERECHA:.1f} pt)")
    print("=" * 72)

    if not ruta.exists():
        print(f"\n  no existe {ruta}. FALLA.")
        return 1

    faltas, colgadas = [], []
    with pdfplumber.open(ruta) as doc:
        for n, pagina in enumerate(doc.pages, 1):
            for ch in _lineas(pagina):
                ultimo = max(ch, key=lambda c: c["x1"])
                exceso = ultimo["x1"] - DERECHA
                if exceso <= TOLERANCIA_LETRA:
                    continue
                texto = "".join(c["text"] for c in ch)[-44:]
                if ultimo["text"] in COLGABLE:
                    colgadas.append((exceso, n, ultimo["text"], texto))
                    if exceso > TOLERANCIA_PUNTUACION:
                        faltas.append((exceso, n, texto, "puntuacion pasada de rosca"))
                else:
                    faltas.append((exceso, n, texto, f"letra «{ultimo['text']}» fuera"))

    print(
        f"\n  puntuacion colgante (aceptable, <= {TOLERANCIA_PUNTUACION:.1f} pt): {len(colgadas)}"
    )
    for e, n, glifo, txt in sorted(colgadas, reverse=True)[:5]:
        print(f"    +{e:5.2f} pt  pag {n:2d}  «{glifo}»  …{txt}")

    print(f"\n  fuera de norma: {len(faltas)}")
    for e, n, txt, motivo in sorted(faltas, reverse=True):
        print(f"    +{e:5.2f} pt  pag {n:2d}  {motivo}\n            …{txt}")

    print(f"\n  VEREDICTO: {'PASA' if not faltas else 'FALLA'}")
    return 0 if not faltas else 1


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    raise SystemExit(revisa(destino))
