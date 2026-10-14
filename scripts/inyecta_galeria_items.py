"""Reescribe la lista ``DATA`` de la galería (``Reports/index.html``) desde lo generado.

La galería pinta una tarjeta por elemento de ``const DATA = [...]``. Hasta la ronda W37 esa línea
se inyectaba a mano (``make gallery-dengue`` sólo lo recordaba), así que cuando la galería de
Dengue dejó de generar sus 4 regiones la lista seguía anunciando 444 gráficos y 12 tarjetas
apuntaban a PNG retirados.

Regla:
  * Dengue sale ENTERO del inventario que escribe ``build_dengue_gallery`` (``_gallery_items.json``).
  * El resto (neuro) se conserva tal cual, pero cada elemento debe tener su PNG: un faltante
    aborta, nunca se publica una tarjeta rota ni se borra en silencio.
  * Orden estable: los elementos no-Dengue en su orden previo y después Dengue en el del inventario.

Uso:
    python scripts/inyecta_galeria_items.py --reports <dashboard>/Reports
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

RE_DATA = re.compile(r"^const DATA = (\[.*\]);$", re.MULTILINE)


def inyecta(reports: Path) -> dict[str, int]:
    """Reescribe ``DATA`` en ``reports/index.html`` y devuelve los conteos por padecimiento."""
    index = reports / "index.html"
    html = index.read_text(encoding="utf-8")
    encontrados = list(RE_DATA.finditer(html))
    if len(encontrados) != 1:
        raise ValueError(
            f"{index}: se esperaba UNA línea `const DATA = [...]`, hay {len(encontrados)}"
        )
    m = encontrados[0]
    previos: list[dict[str, str]] = json.loads(m.group(1))
    dengue: list[dict[str, str]] = json.loads(
        (reports / "dengue" / "_gallery_items.json").read_text(encoding="utf-8")
    )
    if not dengue or any(it.get("p") != "Dengue" for it in dengue):
        raise ValueError("_gallery_items.json vacío o con elementos que no son de Dengue")
    resto = [it for it in previos if it.get("p") != "Dengue"]
    nuevos = resto + dengue
    faltan = [it["f"] for it in nuevos if not (reports / it["f"]).is_file()]
    if faltan:
        raise FileNotFoundError(
            f"{len(faltan)} elemento(s) de la galería sin PNG (p. ej. {faltan[:3]}); no se publica "
            "una tarjeta rota"
        )
    rutas = [it["f"] for it in nuevos]
    if len(set(rutas)) != len(rutas):
        raise ValueError("la galería repetiría un gráfico")
    linea = "const DATA = " + json.dumps(nuevos, ensure_ascii=False) + ";"
    index.write_text(html[: m.start()] + linea + html[m.end() :], encoding="utf-8")
    conteo: dict[str, int] = {}
    for it in nuevos:
        conteo[it["p"]] = conteo.get(it["p"], 0) + 1
    return conteo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--reports", type=Path, required=True, help="Directorio Reports/ del dashboard"
    )
    a = ap.parse_args(argv)
    conteo = inyecta(a.reports)
    print(f"  galería: {sum(conteo.values())} gráficos {json.dumps(conteo, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
