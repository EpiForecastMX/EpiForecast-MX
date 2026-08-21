#!/usr/bin/env python3
"""Arma el ZIP de camera-ready para MICAI 2026 y lo VERIFICA compilandolo desde el ZIP.

MICAI acepta LaTeX solo como .zip con el .tex, la clase, los estilos y las imagenes.
Springer pide nombres cortos, asi que el paquete usa el numero de ponencia: 012.

Lo que hace distinto a comprimir una carpeta: extrae el ZIP en un directorio limpio y
compila desde ahi. Un paquete que no compila fuera de la maquina del autor es el modo
de fallo clasico de esta entrega, y ya nos costo una vez.

Uso:  .venv/bin/python scripts/paper_micai_2026/empaqueta_envio.py
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

RAIZ = Path(__file__).resolve().parents[2]
MICAI = RAIZ / "Congresos/MICAI"
MASTER = MICAI / "paper_camera_ready.tex"
NUMERO = "012"
DESTINO = MICAI / "Envio" / f"{NUMERO}.zip"
SELLO = MICAI / "Envio" / "HASH_ENVIO.txt"


# Misma fecha fija que compila.sh: 2026-08-23T00:00:00Z, el limite de entrega.
# pdfTeX incrusta /CreationDate, asi que sin fijarla el PDF —y con el, el ZIP—
# cambia de hash en cada compilacion. Si se cambia aqui, cambiarla alli tambien.
EPOCA = 1787443200
SELLO_ESPERADO = "D:20260823000000Z"


# Comentarios que SI viajan al maquetador. El resto son notas internas: historia
# de errores, avisos sobre CMT, la variante de doble ciego, apuntes en español.
# Nada de eso afecta al PDF, pero el .tex del ZIP lo lee una persona de Springer.
CONSERVAR = ("% ALT-TEXT",)

# Si alguno de estos sobrevive al saneo, no se empaqueta.
PROHIBIDOS = (">>> REVIEW", ">>> CAMERA-READY", "Claude-Session", "/Users/", "CMT")


def _corta_comentario(linea: str) -> str:
    """Devuelve la linea sin el texto del comentario, conservando el % si lo habia.

    El % NO se borra: en LaTeX un % al final de linea se come el salto, asi que
    quitarlo cambiaria el espaciado. Un %% escapado no abre comentario.
    """
    i, barras = 0, 0
    while i < len(linea):
        c = linea[i]
        if c == "\\":
            barras += 1
        elif c == "%" and barras % 2 == 0:
            return linea[: i + 1]
        else:
            barras = 0
        i += 1
    return linea


def sanea_tex(tex: str) -> str:
    """Quita las notas internas del .tex sin tocar una sola instruccion.

    Que esto es inocuo no se argumenta: empaqueta_envio.py compila la copia saneada
    y exige que el PDF salga byte a byte igual al canonico. Si el saneo cambiase
    algo, el hash no coincidiria y el paquete no se genera.
    """
    salida = []
    for linea in tex.splitlines():
        pelada = linea.lstrip()
        if pelada.startswith("%"):
            if any(pelada.startswith(c) for c in CONSERVAR):
                salida.append(linea)
            continue  # comentario de linea completa: fuera
        salida.append(_corta_comentario(linea))
    return "\n".join(salida) + "\n"


# pdfTeX deriva el /ID del trailer del NOMBRE del fichero, y en el ZIP el master
# se llama 012.tex. Medido: entre el PDF canonico y el compilado desde el ZIP
# difieren 60 bytes y TODOS estan dentro del /ID; el resto, incluidos todos los
# flujos de contenido, es identico. Normalizarlo permite exigir igualdad byte a
# byte de todo lo demas, que es mas fuerte que comparar paginas o texto extraido.
_ID = re.compile(rb"/ID \[<[0-9A-F]+> <[0-9A-F]+>\]")


def _sin_id(pdf: bytes) -> bytes:
    return _ID.sub(b"/ID [<0> <0>]", pdf)


def figuras_referenciadas(tex: str) -> list[str]:
    return sorted(set(re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", tex)))


def construye() -> tuple[Path, list[str]]:
    tex = sanea_tex(MASTER.read_text())
    fugas = sorted({p for p in PROHIBIDOS if p in tex})
    if fugas:
        raise SystemExit(f"el .tex saneado todavia contiene: {fugas}")
    figs = figuras_referenciadas(tex)
    faltan = [f for f in figs if not (MICAI / "Figures" / f).exists()]
    if faltan:
        raise SystemExit(f"faltan figuras referenciadas: {faltan}")

    # ZIP DETERMINISTA. Sin fecha fija, cada regeneracion cambia el sha256 aunque el
    # contenido sea identico, y entonces el hash no sirve para identificar la copia
    # enviada, que es justo para lo que se guarda.
    fecha = (2026, 1, 1, 0, 0, 0)
    piezas = [(f"{NUMERO}.tex", tex.encode())]
    piezas += [(n, (MICAI / n).read_bytes()) for n in ("llncs.cls", "splncs04.bst")]
    piezas += [(f"Figures/{f}", (MICAI / "Figures" / f).read_bytes()) for f in figs]
    pdf = (MICAI / "paper_camera_ready.pdf").read_bytes()
    # El PDF que se envia tiene que venir de compila.sh CON la fecha fija. Si no,
    # lleva la hora real de compilacion y el sha256 del ZIP cambia cada vez que se
    # recompila, que es justo como se desincronizaron los tres hashes. Falla
    # cerrado: mejor no empaquetar que empaquetar algo que no se puede volver a
    # obtener igual.
    if SELLO_ESPERADO.encode() not in pdf:
        raise SystemExit(
            f"el PDF no lleva el sello reproducible {SELLO_ESPERADO}: "
            "recompilalo con Congresos/MICAI/compila.sh antes de empaquetar."
        )
    piezas += [(f"{NUMERO}.pdf", pdf)]

    # Se escribe un CANDIDATO, no el destino final. Antes se escribia directamente
    # sobre Envio/012.zip y se verificaba despues: si la verificacion fallaba, el
    # paquete malo se quedaba en la ruta buena y el ultimo bueno se habia perdido.
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    candidato = DESTINO.with_suffix(".zip.candidato")
    with zipfile.ZipFile(candidato, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in sorted(piezas):
            info = zipfile.ZipInfo(nombre, date_time=fecha)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # unix, para no depender del anfitrion
            info.external_attr = 0o644 << 16
            z.writestr(info, datos)
    return candidato, figs


def verifica(zip_path: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(d)
        nombres = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
        texs = [n for n in nombres if n.endswith(".tex")]
        if len(texs) != 1:
            raise SystemExit(f"el paquete debe llevar UN solo .tex, lleva {texs}")
        if shutil.which("pdflatex") is None:
            # falla cerrado: este script es un gate de entrega, y un paquete sin
            # verificar no puede reportarse como bueno
            raise SystemExit(
                "pdflatex no disponible: el paquete NO se pudo verificar.\n"
                "  Un gate de entrega no puede pasar sin compilar desde el ZIP."
            )
        rc = 0
        for _ in range(3):
            entorno = {**os.environ, "SOURCE_DATE_EPOCH": str(EPOCA), "FORCE_SOURCE_DATE": "1"}
            r = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", texs[0]],
                env=entorno,
                cwd=d,
                capture_output=True,
                timeout=300,
                check=False,
            )
            rc = r.returncode or rc
        log = (d / texs[0]).with_suffix(".log").read_text(encoding="latin-1")
        err = [x for x in log.splitlines() if x.startswith("!")]
        pg = re.findall(r"Output written on .*?\((\d+) pages", log)
        und = len(re.findall(r"[Uu]ndefined (?:citation|reference|control)", log))
        ov = [float(v) for v in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt", log)]
        info = subprocess.run(
            ["pdfinfo", str((d / texs[0]).with_suffix(".pdf"))],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        a4 = "595.276 x 841.89" in info
        # PRUEBA DE IDENTIDAD. El .tex del ZIP va saneado: sin las notas internas
        # del master. Que eso sea inocuo no se argumenta, se demuestra: el PDF que
        # sale de compilar la copia saneada tiene que ser byte a byte el canonico.
        # Solo se puede exigir porque la compilacion es reproducible (fecha fija);
        # si algun dia deja de serlo, esto lo caza antes que nadie.
        salido = (d / texs[0]).with_suffix(".pdf").read_bytes()
        canonico = (MICAI / "paper_camera_ready.pdf").read_bytes()
        identico = _sin_id(salido) == _sin_id(canonico)
        return {
            "identico": identico,
            "nombres": nombres,
            "rc": rc,
            "errores": len(err),
            "undefined": und,
            "paginas": int(pg[0]) if pg else None,
            "overfull_graves": sum(1 for v in ov if v > 15),
            "a4": a4,
        }


def escribe_sello(zip_path: Path) -> tuple[str, int]:
    """Deja el sha256 y el tamanio del ZIP en HASH_ENVIO.txt. Fuente unica."""
    datos = zip_path.read_bytes()
    sha, tam = hashlib.sha256(datos).hexdigest(), len(datos)
    SELLO.write_text(
        "Paquete camera-ready MICAI 2026 · ponencia #12\n"
        "\n"
        f"  sha256  {sha}\n"
        f"  bytes   {tam}\n"
        "\n"
        "Este archivo lo escribe empaqueta_envio.py; no se edita a mano.\n"
        "\n"
        "El PDF se compila con fecha fija (SOURCE_DATE_EPOCH) y el ZIP se arma con\n"
        "fecha y orden fijos, asi que el hash identifica el CONTENIDO: reconstruirlo\n"
        "desde las mismas fuentes vuelve a dar exactamente este valor. Si no coincide,\n"
        "algo cambio en el paper, en las figuras o en la clase.\n"
        "\n"
        "Reconstruir:\n"
        "  Congresos/MICAI/compila.sh\n"
        "  .venv/bin/python scripts/paper_micai_2026/empaqueta_envio.py\n"
        "\n"
        "Comprobar que los documentos declaran este mismo valor:\n"
        "  .venv/bin/python scripts/paper_micai_2026/sello_sincronizado.py\n"
        "\n"
        "Al subir a CMT, guarda el comprobante junto a este archivo.\n"
    )
    # Y se propaga a los documentos que lo citan. Copiarlo a mano fue justo como
    # llegaron a existir tres valores distintos a la vez.
    for doc in (MICAI / "QUE_HACER_EN_CMT.md",):
        if doc.exists():
            texto = doc.read_text()
            nuevo = re.sub(r"\b[0-9a-f]{64}\b", sha, texto)
            if nuevo != texto:
                doc.write_text(nuevo)
    return sha, tam


if __name__ == "__main__":
    # --verifica: modo de SOLO LECTURA sobre el ZIP que ya existe. Lo usa la
    # auditoria, que no tiene por que reconstruir el artefacto ni reescribir su
    # sello: una auditoria que muta lo que audita no es una auditoria.
    solo_lee = "--verifica" in sys.argv
    if solo_lee:
        if not DESTINO.exists():
            print(f"no existe {DESTINO.relative_to(RAIZ)}; construyelo primero.")
            sys.exit(1)
        z = DESTINO
    else:
        z, figs = construye()
    v = verifica(z)
    print("=" * 72)
    print(f"PAQUETE DE ENVIO — {DESTINO.relative_to(RAIZ)}")
    print("=" * 72)
    print(
        f"  {z.stat().st_size / 1024:.0f} KB · sha256 {hashlib.sha256(z.read_bytes()).hexdigest()[:16]}"
    )
    print("  contenido:")
    for n in v["nombres"]:
        print(f"     {n}")
    print(
        f"\n  compilado DESDE EL ZIP: {v['paginas']} paginas · rc={v['rc']} · "
        f"{v['errores']} errores · {v['undefined']} undefined · "
        f"{v['overfull_graves']} overfull >15pt · A4 {'si' if v['a4'] else 'NO'}"
    )
    print(
        "  .tex saneado (sin notas internas): PDF "
        + ("byte-identico al canonico salvo el /ID" if v["identico"] else "DISTINTO del canonico")
    )
    malo = (
        v["rc"]
        or v["errores"]
        or v["undefined"]
        or v["overfull_graves"]
        or not v["a4"]
        or v["paginas"] is None
        or v["paginas"] > 20
        or not v["identico"]
    )
    # El sello lo ESCRIBE este script, no una mano. Antes se copiaba a mano en
    # HASH_ENVIO.txt y en QUE_HACER_EN_CMT.md, y los tres valores acabaron
    # distintos entre si. Ahora hay una sola fuente y sello_sincronizado.py
    # comprueba que los documentos digan lo que dice el ZIP.
    if solo_lee:
        print("  (modo verificacion: no se reconstruyo ni se reescribio el sello)")
    elif malo:
        z.unlink(missing_ok=True)
        print("  candidato descartado; el paquete anterior sigue intacto")
    else:
        # Reemplazo atomico: o esta el paquete viejo entero, o el nuevo entero.
        z.replace(DESTINO)
        escribe_sello(DESTINO)
        print(f"  sello escrito en {SELLO.relative_to(RAIZ)}")
    print("  VEREDICTO:", "FALLA" if malo else "PASA")
    sys.exit(1 if malo else 0)
