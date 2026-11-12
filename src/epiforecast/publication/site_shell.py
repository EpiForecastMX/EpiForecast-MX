"""Cabecera y pie comunes del sitio para los generadores HTML del backend.

El frontend (EpiForecast-IMSS-Dashboard) es la ÚNICA fuente del marcado de la cabecera y el pie:
``scripts/site_shell.mjs`` los renderiza desde ``assets/site/shell.config.json`` y deja, por
familia de página, los fragmentos ya renderizados para una página de la raíz en
``assets/site/shell.fragments.json``. Este módulo sólo los estampa entre los marcadores
``<!-- site:header:start/end -->`` y ``<!-- site:footer:start/end -->``: no reimplementa el
renderizado, así que un generador del backend y ``site_shell.mjs --check`` producen los mismos
bytes. Sin red ni Node.

Uso típico en un generador que escribe una página de la raíz del dashboard::

    from epiforecast.publication.site_shell import cargar_fragmentos, estampa
    html = estampa(html, "editorial", cargar_fragmentos(dashboard))

Las páginas que el frontend tiene en su manifiesto también las estampa ``site_shell.mjs``; si un
generador escribe una página sin estampar, ``site_shell.mjs --check`` (en el build) lo detecta.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FRAGMENTOS = Path("assets/site/shell.fragments.json")
ESQUEMA = "epiforecast.site_shell_fragments.v1"
BLOQUES_POR_VARIANTE = {
    "default": ("header", "footer"),
    "app": ("header",),
    "micrositio": ("header", "footer"),
}


class ShellError(ValueError):
    """Fragmentos ausentes o inválidos, o una página sin los marcadores esperados."""


def cargar_fragmentos(dashboard: Path) -> dict[str, Any]:
    """Lee y valida los fragmentos del dashboard. Falla cerrado con un mensaje accionable."""
    ruta = Path(dashboard) / FRAGMENTOS
    if not ruta.is_file():
        raise ShellError(
            f"falta {ruta}: genere los fragmentos en el dashboard con `node scripts/site_shell.mjs`"
        )
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    if datos.get("schema") != ESQUEMA:
        raise ShellError(f"{ruta}: esquema {datos.get('schema')!r}, se esperaba {ESQUEMA!r}")
    familias = datos.get("families")
    if not isinstance(familias, dict) or not familias:
        raise ShellError(f"{ruta}: sin familias")
    for nombre, fam in familias.items():
        variante = fam.get("variant")
        if variante not in BLOQUES_POR_VARIANTE:
            raise ShellError(f"{ruta}: familia {nombre} con variante desconocida {variante!r}")
        for bloque in BLOQUES_POR_VARIANTE[variante]:
            if not isinstance(fam.get(bloque), str) or not fam[bloque].strip():
                raise ShellError(f"{ruta}: familia {nombre} sin bloque {bloque}")
    return datos


def _estampa_bloque(html: str, nombre: str, bloque: str) -> str:
    inicio = f"<!-- site:{nombre}:start -->"
    fin = f"<!-- site:{nombre}:end -->"
    n_inicio, n_fin = html.count(inicio), html.count(fin)
    if n_inicio != 1 or n_fin != 1:
        raise ShellError(f"marcadores site:{nombre} {n_inicio}/{n_fin} (se esperaba 1/1)")
    i = html.index(inicio) + len(inicio)
    j = html.index(fin)
    if j < i:
        raise ShellError(f"marcadores site:{nombre} invertidos")
    return f"{html[:i]}\n{bloque}\n{html[j:]}"


def estampa(html: str, familia: str, fragmentos: dict[str, Any]) -> str:
    """Estampa la cabecera (y el pie, si la variante lo lleva) de ``familia`` en ``html``.

    Idempotente: estampar dos veces da los mismos bytes. Los fragmentos son para una página de la
    raíz del sitio (rutas relativas sin ``../``); para otra profundidad, use el manifiesto del
    frontend (``site_shell.mjs --page``).
    """
    familias = fragmentos["families"]
    if familia not in familias:
        raise ShellError(f"familia desconocida {familia!r}; disponibles: {sorted(familias)}")
    fam = familias[familia]
    bloques = BLOQUES_POR_VARIANTE[fam["variant"]]
    if "footer" not in bloques and "<!-- site:footer:start -->" in html:
        raise ShellError(f"la familia {familia} (variante {fam['variant']}) no lleva pie")
    for bloque in bloques:
        html = _estampa_bloque(html, bloque, fam[bloque])
    return html


def marcadores(variante: str = "default") -> dict[str, str]:
    """Marcadores vacíos para una plantilla nueva: {"header": ..., "footer": ...}."""
    if variante not in BLOQUES_POR_VARIANTE:
        raise ShellError(f"variante desconocida {variante!r}")
    return {
        b: f"<!-- site:{b}:start -->\n<!-- site:{b}:end -->"
        for b in BLOQUES_POR_VARIANTE[variante]
    }
