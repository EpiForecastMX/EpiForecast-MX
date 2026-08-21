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

# Documentos que citan el sello. Cualquier sha256 de 64 caracteres que aparezca
# en ellos tiene que ser el del ZIP: no hay motivo para que citen otro.
DOCUMENTOS = [
    MICAI / "Envio" / "HASH_ENVIO.txt",
    MICAI / "QUE_HACER_EN_CMT.md",
]

SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


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
    for doc in DOCUMENTOS:
        if not doc.exists():
            print(f"\n  {doc.name}: no existe. FALLA.")
            fallos += 1
            continue
        texto = doc.read_text()
        citados = set(SHA256.findall(texto))
        if not citados:
            print(f"\n  {doc.name}: no cita ningun sha256. FALLA.")
            fallos += 1
            continue
        malos = sorted(citados - {real})
        print(f"\n  {doc.name}: cita {len(citados)} sha256")
        for c in sorted(citados):
            marca = "ok" if c == real else "NO COINCIDE"
            print(f"    {c[:16]}...  {marca}")
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
