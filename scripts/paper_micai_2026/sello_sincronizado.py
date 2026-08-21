"""Gate: el sha256 que declaran los documentos tiene que ser el del ZIP real.

Nace de un fallo real. El sello se copiaba a mano en dos sitios y acabo habiendo
tres valores distintos a la vez: el ZIP valia 755bc308..., HASH_ENVIO.txt
declaraba 615e6a04... y QUE_HACER_EN_CMT.md seguia en 6d6eaa5e.... Ningun control
lo veia, porque todos miraban el paquete y ninguno miraba lo que se decia de el.

La causa de fondo era que el PDF llevaba la hora real de compilacion, asi que el
ZIP cambiaba de hash en cada recompilacion y los documentos quedaban viejos sin
que nadie tocara nada. Eso ya esta arreglado (compila.sh fija SOURCE_DATE_EPOCH),
pero el gate se queda: es la comprobacion barata de que no vuelva a pasar.

HASH_ENVIO.txt lo escribe empaqueta_envio.py, asi que ese no puede desviarse.
Los demas documentos citan el hash a mano y si pueden.

Uso:
    python scripts/paper_micai_2026/sello_sincronizado.py
Devuelve 0 si todos coinciden, 1 si alguno miente.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[2]
MICAI = RAIZ / "Congresos" / "MICAI"
ZIP = MICAI / "Envio" / "012.zip"


# Los documentos NO se enumeran a mano: se descubren. La lista fija se quedo corta
# --AUDITORIA_FINAL_CIERRE.md citaba un hash caducado y nadie lo miraba-- y volveria
# a quedarse corta con el siguiente documento que alguien escriba.
def documentos() -> list[Path]:
    return sorted(
        r
        for patron in ("*.md", "*.txt")
        for r in MICAI.rglob(patron)
        if "_archive" not in r.parts and SHA256.search(r.read_text(errors="ignore"))
    )


SHA256 = re.compile(r"\b[0-9a-f]{64}\b")

# No todo sha256 de estos documentos es el del paquete: la auditoria cita tambien el
# del CSV de la ablacion publica, y eso es correcto. Solo se exige coincidencia a los
# que se presentan COMO el del ZIP, es decir los que aparecen cerca de su nombre o de
# una etiqueta de sello. Exigirlo a todos daria un falso positivo.
VENTANA = 3  # lineas hacia atras donde buscar la atribucion
ATRIBUYE = re.compile(r"012\.zip|sha256|SHA-256|Paquete camera-ready", re.I)


def hashes_del_paquete(texto: str) -> list[str]:
    lineas = texto.splitlines()
    encontrados = []
    for i, linea in enumerate(lineas):
        for m in SHA256.finditer(linea):
            contexto = "\n".join(lineas[max(0, i - VENTANA) : i + 1])
            if ATRIBUYE.search(contexto):
                encontrados.append(m.group(0))
    return encontrados


def propaga(texto: str, sha: str) -> str:
    """Reescribe SOLO los hashes atribuidos al paquete. Los ajenos no se tocan."""
    lineas = texto.splitlines(keepends=True)
    for i, linea in enumerate(lineas):
        if not SHA256.search(linea):
            continue
        contexto = "".join(lineas[max(0, i - VENTANA) : i + 1])
        if ATRIBUYE.search(contexto):
            lineas[i] = SHA256.sub(sha, linea)
    return "".join(lineas)


def revisa() -> int:
    print("=" * 72)
    print("SELLO SINCRONIZADO — el ZIP y lo que los documentos dicen de el")
    print("=" * 72)

    if not ZIP.exists():
        print(f"\n  no existe {ZIP.relative_to(RAIZ)}. FALLA.")
        return 1

    datos = ZIP.read_bytes()
    real = hashlib.sha256(datos).hexdigest()
    print(f"\n  ZIP real          {real}")
    print(f"  bytes             {len(datos)}")

    fallos = 0
    for doc in documentos():
        if not doc.exists():
            print(f"\n  {doc.name}: no existe. FALLA.")
            fallos += 1
            continue
        texto = doc.read_text(errors="ignore")
        citados = set(hashes_del_paquete(texto))
        otros = len(set(SHA256.findall(texto)) - citados)
        if not citados:
            print(f"\n  {doc.relative_to(MICAI)}: cita sha256 pero ninguno como el del paquete")
            continue
        malos = sorted(citados - {real})
        extra = f" (+{otros} ajenos, no se revisan)" if otros else ""
        print(f"\n  {doc.relative_to(MICAI)}: {len(citados)} del paquete{extra}")
        for c in sorted(citados):
            print(f"    {c[:16]}...  {'ok' if c == real else 'NO COINCIDE'}")
        if malos:
            fallos += 1

    # El tamanio se declara aparte del hash y tambien se copiaba a mano.
    sello = MICAI / "Envio" / "HASH_ENVIO.txt"
    if sello.exists():
        tam = re.search(r"bytes\s+(\d+)", sello.read_text())
        if not tam:
            print("\n  HASH_ENVIO.txt no declara el tamanio. FALLA.")
            fallos += 1
        elif int(tam.group(1)) != len(datos):
            print(
                f"\n  HASH_ENVIO.txt declara {tam.group(1)} bytes, el ZIP tiene {len(datos)}. FALLA."
            )
            fallos += 1

    print(f"\n  VEREDICTO: {'PASA' if not fallos else 'FALLA'}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    raise SystemExit(revisa())
