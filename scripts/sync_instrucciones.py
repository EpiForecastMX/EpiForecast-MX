"""Mantiene AGENTS.md y GEMINI.md como espejos exactos de CLAUDE.md.

CLAUDE.md es la única fuente que se edita. Los espejos sólo cambian el título
y añaden un aviso de que se generan. Uso:

    python scripts/sync_instrucciones.py          # regenera los espejos
    python scripts/sync_instrucciones.py --check  # falla si alguno divergió
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = "CLAUDE.md"
ESPEJOS = ("AGENTS.md", "GEMINI.md")
TITULO_FUENTE = "# CLAUDE.md: Guia de Desarrollo EpiForecast-MX"


def espejo(texto: str, nombre: str) -> str:
    """Devuelve el contenido que debe tener el espejo ``nombre``."""
    if texto.count(TITULO_FUENTE + "\n") != 1:
        raise ValueError(f"{FUENTE} debe contener una sola vez el título {TITULO_FUENTE!r}")
    titulo = TITULO_FUENTE.replace(FUENTE, nombre, 1)
    aviso = (
        f"> Espejo generado de `{FUENTE}`: no editar aquí. Editar `{FUENTE}` y correr "
        "`make sync-instrucciones`.\n"
    )
    return texto.replace(TITULO_FUENTE + "\n", f"{titulo}\n\n{aviso}", 1)


def divergentes(raiz: Path = RAIZ) -> list[str]:
    """Lista los espejos cuyo contenido no coincide con el generado."""
    texto = (raiz / FUENTE).read_text(encoding="utf-8")
    fuera = []
    for nombre in ESPEJOS:
        ruta = raiz / nombre
        actual = ruta.read_text(encoding="utf-8") if ruta.exists() else None
        if actual != espejo(texto, nombre):
            fuera.append(nombre)
    return fuera


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="sólo comprobar, sin escribir")
    args = parser.parse_args()
    fuera = divergentes()
    if args.check:
        if fuera:
            print(f"Divergen de {FUENTE}: {', '.join(fuera)}. Corre make sync-instrucciones.")
            return 1
        print(f"Espejos sincronizados con {FUENTE}.")
        return 0
    texto = (RAIZ / FUENTE).read_text(encoding="utf-8")
    for nombre in ESPEJOS:
        (RAIZ / nombre).write_text(espejo(texto, nombre), encoding="utf-8")
    print(f"Regenerados: {', '.join(ESPEJOS)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
