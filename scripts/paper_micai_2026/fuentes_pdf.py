"""Gate: ninguna fuente Type 3, todas incrustadas, ligaduras extraibles.

Nace de un fallo real. El PDF final llevaba 15 recursos Type 3 en las 20 paginas.
El cuerpo usa Computer Modern en codificacion T1 y esta instalacion no tenia
cm-super, asi que pdfTeX genero mapas de bits PK y los incrusto como Type 3.
Springer los rechaza: no escalan y no se pueden buscar.

El gate de tipografia no lo veia porque mira el TAMANIO de los glifos dentro de
las figuras, no el TIPO de las fuentes del documento. Son dos preguntas distintas
sobre el mismo PDF y hacian falta las dos.

Se arreglo instalando cm-super en el arbol de usuario, que es exactamente
Computer Modern en Type 1: mismas metricas, ni una pagina de diferencia.
    tlmgr --usermode --repository <tlnet-final de tu version> install cm-super

Comprueba tres cosas sobre el PDF ensamblado:
  1. cero fuentes Type 3;
  2. todas incrustadas (si no, el maquetador ve otra cosa que tu);
  3. las ligaduras se extraen como texto ("cutoff", no "cuto").

La tercera esta aqui porque ya fallo una vez por otro motivo: las CM en T1 rompian
la extraccion y lo arreglo \\usepackage{cmap}. Si alguien quita ese paquete, esto
lo caza.

Uso:
    python scripts/paper_micai_2026/fuentes_pdf.py [ruta.pdf]
Devuelve 0 si todo esta limpio, 1 si algo falla.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[2]
PDF = RAIZ / "Congresos" / "MICAI" / "paper_camera_ready.pdf"

# Palabras del paper que llevan ligadura (ff, fi, ffi). Si la extraccion se rompe
# salen mutiladas y no se encuentran.
LIGADURAS = ["cutoff", "difference", "specific", "efficient", "classification"]


def _fuentes(ruta: Path) -> list[dict[str, str]]:
    salida = subprocess.run(
        ["pdffonts", str(ruta)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    filas = []
    for linea in salida[2:]:
        if not linea.strip():
            continue
        # pdffonts alinea por columnas y el nombre puede llevar espacios; los seis
        # campos de la derecha son fijos: emb sub uni object ID.
        partes = linea.split()
        if len(partes) < 6:
            continue
        filas.append(
            {
                "nombre": partes[0],
                "tipo": " ".join(partes[1:-5]).strip(),
                "emb": partes[-5],
            }
        )
    return filas


def revisa(ruta: Path) -> int:
    print("=" * 72)
    print("FUENTES DEL PDF — sin Type 3, todas incrustadas, ligaduras extraibles")
    print("=" * 72)

    if shutil.which("pdffonts") is None:
        print("\n  pdffonts no disponible: NO se pudo comprobar. FALLA.")
        return 1
    if not ruta.exists():
        print(f"\n  no existe {ruta}. FALLA.")
        return 1

    # Falla cerrado: si pdffonts no puede leer el PDF, el gate NO opina que este
    # limpio. Antes reventaba con traza, que da rc=1 igual pero no dice nada util.
    try:
        fuentes = _fuentes(ruta)
    except subprocess.CalledProcessError as e:
        print(f"\n  pdffonts no pudo leer el PDF (rc={e.returncode}). FALLA.")
        return 1
    if not fuentes:
        print("\n  pdffonts no reporto ninguna fuente. FALLA.")
        return 1

    tipos: dict[str, int] = {}
    for f in fuentes:
        # el tipo real es la ultima palabra del campo, salvo Type 1/Type 3
        tipos[f["tipo"]] = tipos.get(f["tipo"], 0) + 1
    print(f"\n  {len(fuentes)} fuentes:")
    for t, n in sorted(tipos.items(), key=lambda kv: -kv[1]):
        print(f"    {n:3d}  {t}")

    fallos = 0

    type3 = [f for f in fuentes if "Type 3" in f["tipo"]]
    print(f"\n  Type 3            : {len(type3)}")
    for f in type3:
        print(f"    {f['nombre']} <-- Springer no lo acepta")
    if type3:
        fallos += 1

    sueltas = [f for f in fuentes if f["emb"] != "yes"]
    print(f"  sin incrustar     : {len(sueltas)}")
    for f in sueltas:
        print(f"    {f['nombre']} <-- el maquetador veria otra cosa")
    if sueltas:
        fallos += 1

    texto = subprocess.run(
        ["pdftotext", str(ruta), "-"], capture_output=True, text=True, check=False
    ).stdout
    rotas = [p for p in LIGADURAS if not re.search(rf"\b{p}\b", texto)]
    print(f"  ligaduras rotas   : {len(rotas)}")
    for p in rotas:
        print(f"    «{p}» no se extrae <-- revisa \\usepackage{{cmap}}")
    if rotas:
        fallos += 1

    print(f"\n  VEREDICTO: {'PASA' if not fallos else 'FALLA'}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    raise SystemExit(revisa(destino))
