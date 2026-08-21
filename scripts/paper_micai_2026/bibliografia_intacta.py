"""Gate: la bibliografia entera y las citas multiples en orden numerico.

Dos comprobaciones sobre la misma lista de referencias del PDF ensamblado.

PRIMERA: la lista no puede quedar partida por un flotante.

Nace de un fallo real. La Tabla 4 vivia dentro del apendice, declarada como
flotante `[!h]`; no cabia en su pagina, LaTeX la diferia y acababa impresa
entre las referencias [2] y [3]. El PDF compilaba sin un solo aviso: ni error,
ni referencia sin resolver, ni overfull. Ningun control existente lo veia.

Se mide sobre el PDF ensamblado, que es el unico sitio donde el problema
existe: en la fuente .tex no hay nada anomalo que detectar.

El invariante es "la bibliografia es contigua", no "la tabla va antes de
References". Son distintos: la solucion final coloca el apendice DESPUES de la
bibliografia, asi que el pie de la Tabla 4 aparece despues de la ultima
referencia y eso esta bien. Lo que nunca puede pasar es que un pie de figura o
de tabla caiga en medio de la lista.

SEGUNDA: toda cita multiple va en orden numerico ascendente. Lo pide la guia de
Springer y se habia colado en tres grupos: [23,9], [4,19,14] y [24,2]. El orden lo
fija el orden de las claves dentro de \\cite{}, porque splncs04 no las reordena;
como la bibliografia es alfabetica, la clave y el numero no van a la par y el
desorden no se ve leyendo la fuente. Por eso se mide sobre el PDF.

Uso:
    python scripts/paper_micai_2026/bibliografia_intacta.py [ruta.pdf]
Devuelve 0 si la lista esta intacta y las citas ordenadas, 1 si no.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

import pdfplumber  # noqa: I001

RAIZ = Path(__file__).resolve().parents[2]
PDF = RAIZ / "Congresos" / "MICAI" / "paper_camera_ready.pdf"

CAPTION_PT = 9.0  # LNCS compone los pies de figura y tabla a 9 pt
TITULO_PT = 12.0  # y los encabezados de seccion a 12
# El numero de referencia se alinea a la DERECHA dentro de su caja: los de una
# cifra arrancan en 139.4 y los de dos en 134.8. Medido, no supuesto: con la
# tolerancia estrecha de antes se perdian 9 de las 28 entradas.
MARGEN_MIN, MARGEN_MAX = 134.0, 140.5
ENTRADA = re.compile(r"^\d+\.$")


def _posicion(pagina: int, top: float) -> tuple[int, float]:
    return (pagina, top)


def revisa(ruta: Path) -> int:
    encabezado: tuple[int, float] | None = None
    entradas: list[tuple[int, float, str]] = []
    pies: list[tuple[int, float, str]] = []

    with pdfplumber.open(ruta) as doc:
        for n, pagina in enumerate(doc.pages, 1):
            palabras = pagina.extract_words(extra_attrs=["size"])
            for i, p in enumerate(palabras):
                izquierda = MARGEN_MIN <= p["x0"] <= MARGEN_MAX
                # el encabezado «References» de la bibliografia
                if p["text"] == "References" and abs(p["size"] - TITULO_PT) < 0.5:
                    encabezado = _posicion(n, p["top"])
                # Cada entrada numerada: pegada al margen Y a 9 pt. Sin el filtro
                # de tamanio tambien entraban los items numerados del cuerpo, que
                # van a 10 pt, y el tramo "bibliografia" se estiraba hasta la
                # pagina 8, tragandose los pies de las Tablas 1-3 como si fuesen
                # intrusos. Ademas solo cuentan las que van DESPUES del encabezado.
                if izquierda and ENTRADA.match(p["text"]) and abs(p["size"] - CAPTION_PT) < 0.3:
                    entradas.append((n, p["top"], p["text"]))
                # Pies de figura y de tabla. NO se filtran por posicion: un pie
                # corto se compone centrado, no pegado al margen, y filtrar por x
                # dejaba fuera justo el de la Tabla 4, que es el que dio problemas.
                # A 9 pt y seguido de un numero solo hay pies.
                if (
                    abs(p["size"] - CAPTION_PT) < 0.3
                    and p["text"] in ("Fig.", "Table")
                    and i + 1 < len(palabras)
                    and re.match(r"^\d+\.", palabras[i + 1]["text"])
                ):
                    pies.append((n, p["top"], f"{p['text']} {palabras[i + 1]['text']}"))

    print("=" * 72)
    print("BIBLIOGRAFIA INTACTA — ningun flotante puede partir la lista")
    print("=" * 72)

    if encabezado is None:
        print("\n  No se encontro el encabezado «References». FALLA.")
        return 1
    if not entradas:
        print("\n  No se encontro ninguna entrada numerada. FALLA.")
        return 1

    entradas = [e for e in entradas if _posicion(e[0], e[1]) > encabezado]
    if not entradas:
        print("\n  No hay entradas numeradas despues de «References». FALLA.")
        return 1
    primera = min(_posicion(p, t) for p, t, _ in entradas)
    ultima = max(_posicion(p, t) for p, t, _ in entradas)
    print(f"\n  «References»      pagina {encabezado[0]}")
    print(f"  entradas          {len(entradas)}: de la pagina {primera[0]} a la {ultima[0]}")

    intrusos = [(p, t, e) for p, t, e in pies if primera <= _posicion(p, t) <= ultima]
    print(f"  pies de figura/tabla dentro de ese tramo: {len(intrusos)}")
    for p, t, e in intrusos:
        print(f"    pagina {p}, y={t:.0f}: «{e}» parte la lista")

    fuera = [(p, t, e) for p, t, e in pies if _posicion(p, t) > ultima]
    for p, _t, e in fuera:
        print(f"  «{e}» en la pagina {p}, despues de la ultima referencia (correcto)")

    fallos = len(intrusos)

    # Citas multiples en orden ascendente. Se leen del texto extraido: un grupo es
    # una lista de numeros entre corchetes separados por comas.
    with pdfplumber.open(ruta) as doc:
        texto = "\n".join((pg.extract_text() or "") for pg in doc.pages)
    grupos = re.findall(r"\[(\d+(?:,\d+)+)\]", texto)
    desordenados = []
    for g in grupos:
        nums = [int(x) for x in g.split(",")]
        if nums != sorted(nums):
            desordenados.append((g, ",".join(str(x) for x in sorted(nums))))
    print(f"\n  citas multiples   : {len(grupos)}")
    for malo, bueno in desordenados:
        print(f"    [{malo}] deberia ser [{bueno}]")
    fallos += len(desordenados)

    veredicto = "PASA" if not fallos else "FALLA"
    print(f"\n  VEREDICTO: {veredicto}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    raise SystemExit(revisa(destino))
