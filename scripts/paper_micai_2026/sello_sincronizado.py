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

# La atribucion tiene que ser EXPLICITA. Con `sha256` a secas como marcador, una
# linea tan normal como "SHA-256 del CSV de ablacion:" contaba como si el hash
# fuese el del paquete, y propaga() lo habria pisado al resellar: un hash
# cientifico destruido por el mecanismo que existe para cuidar los sellos.
# Cada alternativa de aqui nombra el paquete; ninguna es una etiqueta generica.
ATRIBUYE = re.compile(
    r"012\.zip|paquete camera-ready|sha256 del paquete|hash del paquete|sello del paquete",
    re.I,
)


def hashes_del_paquete(texto: str) -> list[str]:
    lineas = texto.splitlines()
    encontrados = []
    for i, linea in enumerate(lineas):
        for m in SHA256.finditer(linea):
            contexto = "\n".join(lineas[max(0, i - VENTANA) : i + 1])
            if ATRIBUYE.search(contexto):
                encontrados.append(m.group(0))
    return encontrados


# El TAMANIO se declara aparte del hash y tambien caduca. Un documento llego a
# decir 701,662 bytes con el ZIP en 701,531 y el gate daba verde, porque solo
# comprobaba el tamanio de HASH_ENVIO.txt.
#
# La etiqueta tiene que estar en la MISMA LINEA que el numero, no en una ventana
# de contexto. Con `size` generico y ventana de tres lineas, un «Sample size:
# 123,456 observations» escrito cerca del bloque del sello contaba como tamanio
# del paquete, y propaga() lo reescribia a 701,684: un dato cientifico destruido
# por el mecanismo que existe para cuidar los sellos. Mismo error que ya se
# corrigio en la atribucion del hash, repetido aqui.
#
# Las dos formas que usan de verdad los documentos, y ambas llevan «bytes» al lado:
#     bytes   701684
#     - Tamanio: 701,684 bytes.
TAMANIO_ETIQUETADO = re.compile(
    r"(?:\bbytes\b[^\d\n]{0,12}(\d{1,3}(?:[.,\u00a0 ]\d{3})+|\d{4,})"
    r"|(\d{1,3}(?:[.,\u00a0 ]\d{3})+|\d{4,})[^\d\n]{0,12}\bbytes\b)",
    re.I,
)


def _entero(s: str) -> int:
    return int(re.sub(r"[.,\u00a0 ]", "", s))


def _numero(m: re.Match[str]) -> str:
    return m.group(1) or m.group(2)


def tamanios_del_paquete(texto: str) -> list[int]:
    """Tamanios presentados como el del ZIP: «bytes» en la misma linea y el
    paquete nombrado en el contexto. Sin las dos cosas, el numero no se toca."""
    lineas = texto.splitlines()
    salida = []
    for i, linea in enumerate(lineas):
        contexto = "\n".join(lineas[max(0, i - VENTANA) : i + 1])
        if ATRIBUYE.search(contexto):
            salida += [_entero(_numero(m)) for m in TAMANIO_ETIQUETADO.finditer(linea)]
    return salida


def propaga(texto: str, sha: str, tam: int | None = None) -> str:
    """Reescribe SOLO lo atribuido al paquete: el hash y, si se da, el tamanio."""
    lineas = texto.splitlines(keepends=True)
    for i in range(len(lineas)):
        contexto = "".join(lineas[max(0, i - VENTANA) : i + 1])
        if not ATRIBUYE.search(contexto):
            continue
        if SHA256.search(lineas[i]):
            lineas[i] = SHA256.sub(sha, lineas[i])
        if tam is not None:
            lineas[i] = TAMANIO_ETIQUETADO.sub(
                lambda m: m.group(0).replace(_numero(m), _formatea(_numero(m), tam)),
                lineas[i],
            )
    return "".join(lineas)


def _formatea(original: str, tam: int) -> str:
    """Conserva el separador de miles que ya usaba el documento."""
    sep = next((c for c in original if c in ".,\u00a0 "), "")
    s = str(tam)
    return f"{s[:-3]}{sep}{s[-3:]}" if sep else s


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

    # Los TAMANIOS, en todos los documentos y con la misma regla de atribucion.
    print(f"\n  tamanios declarados (real {len(datos)}):")
    vistos = 0
    for doc in documentos():
        for t_dec in tamanios_del_paquete(doc.read_text(errors="ignore")):
            vistos += 1
            ok = t_dec == len(datos)
            print(f"    {doc.relative_to(MICAI)}: {t_dec}  {'ok' if ok else 'NO COINCIDE'}")
            if not ok:
                fallos += 1
    if not vistos:
        print("    ninguno; al menos HASH_ENVIO.txt deberia declararlo. FALLA.")
        fallos += 1

    print(f"\n  VEREDICTO: {'PASA' if not fallos else 'FALLA'}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    raise SystemExit(revisa())
