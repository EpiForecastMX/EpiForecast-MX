"""Lleva una página editorial de la plantilla vieja al sistema visual común del sitio.

Un solo algoritmo para dos usos:

* la migración del frontend (una vez, sobre las páginas existentes), y
* los generadores del backend que escriben páginas editoriales (validación semanal, bitácora,
  reporte de resultados, comparación de modelos), para que una regeneración no reintroduzca la
  barra vieja ni el tema oscuro.

Sólo cambia chrome y presentación, nunca el contenido:

1. ``<head>``: retira las fuentes externas y ``editorial.css`` viejo; enlaza ``assets/site/site.css``
   y el ``editorial.css`` claro con las versiones que declara el manifiesto del frontend
   (``shell.fragments.json``), así el bump de caché no lo pisa nadie.
2. Barra vieja (``<nav class="nav" id="nav">``) y su menú móvil: fuera; en su lugar, enlace de salto
   y marcadores de la cabecera común.
3. Pie viejo: en las páginas del corpus del RAG (``epibot/scripts/lib/corpus.mjs``) se conserva su
   contenido como colofón (``div.legacy-colophon``), porque forma parte del texto indexado; en las
   demás (``colofon=False``) se retira. Después van los marcadores del pie común.
4. ``<style>`` en línea, atributos ``style`` y literales de color en ``<script>``: la paleta oscura
   del template se traduce a la clara, y las reglas de la barra vieja se retiran (sus clases coinciden
   con las de la cabecera común). Los selectores de elemento ``nav``/``header``/``footer`` se acotan
   con ``:not(.site-…)`` para no alcanzar el chrome común. Las compensaciones de la barra fija
   vieja (``padding-top: 64px`` del ``body``, ``top: 64px`` de barras pegajosas) pasan a la altura
   real de la cabecera común (``--site-header-h``, que publica ``site-nav.js``) y las barras
   pegajosas propias quedan por debajo de ella (``z-index`` ≤ :data:`Z_LOCAL_MAX`), sin subir la
   cabecera a valores gigantes.
5. ``assets/site/site-nav.js`` al final del ``<body>``.

Idempotente: una página que ya lleva los marcadores sólo se vuelve a estampar (y se traduce la
paleta de lo que un generador haya inyectado en una plantilla ya migrada).
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Any

from epiforecast.publication.site_shell import FRAGMENTOS, ShellError, cargar_fragmentos, estampa

# Paleta del template oscuro (Clinical Indigo) -> sistema claro (assets/site/site.css).
PALETA_HEX = {
    "#0e1424": "#fafbf7",
    "#0a0e18": "#fafbf7",
    "#131c30": "#fafbf7",
    "#121a2c": "#ffffff",
    "#18223a": "#f1f6ef",
    "#1c2740": "#ffffff",
    "#243150": "#dbe3dc",
    "#e7ecf5": "#173c33",
    "#eaeff8": "#173c33",
    "#9fb0ce": "#40594f",
    "#b9c5dd": "#40594f",
    "#6e82a6": "#53675e",
    "#8094b8": "#53675e",
    "#44567a": "#5b6f66",
    "#5b8def": "#2f5f9e",
    "#6aa0ff": "#2f5f9e",
    "#2dd4bf": "#0f6e66",
    "#f472b6": "#a3367a",
    "#f59e0b": "#9a5200",
    "#fbbf24": "#7d4400",
    # Acentos pastel pensados para fondo oscuro (estados, diferencias, modelos): tono AA sobre claro
    # con la misma semántica (rojo = crítico/peor, verde = limpio/mejor, ámbar = aviso) y sin
    # fundir dos series de un mismo gráfico (Ensemble ≠ NB-GLM, LightGBM ≠ DeepAR).
    "#f87171": "#b0322f",
    "#34d399": "#3d6b1f",
    "#4ade80": "#3d6b1f",
    "#fcd34d": "#7d4400",
    "#fb923c": "#c2410c",
    "#8b9dff": "#4b52b8",
    "#a78bfa": "#6a4aa6",
    # Resaltado de sintaxis de los bloques de código (Material y Catppuccin, ambos oscuros).
    "#c792ea": "#6a4aa6",
    "#82aaff": "#2f5f9e",
    "#c3e88d": "#3d6b1f",
    "#546e7a": "#53675e",
    "#f78c6c": "#9a4a00",
    "#89ddff": "#1d5f86",
    "#6c7086": "#53675e",
    "#cba6f7": "#6a4aa6",
    "#a6e3a1": "#3d6b1f",
    "#fab387": "#9a4a00",
    "#89b4fa": "#2f5f9e",
    "#cdd6f4": "#173c33",
    "#e0e0e0": "#173c33",
    "#1e1e2e": "#f1f6ef",
    # Fondos decorativos oscuros de héroes y páginas sueltas (degradados, tarjetas de cabecera).
    "#1b1733": "#f1f6ef",
    "#1a2844": "#f1f6ef",
    "#0a1628": "#fafbf7",
    "#1a2d58": "#f1f6ef",
    "#1a0a12": "#fafbf7",
    "#101625": "#fafbf7",
    "#1a2337": "#ffffff",
    "#16203a": "#f1f6ef",
    "#e5eaf5": "#173c33",
    # Paleta oscura propia de comparacion_rondas.html (enlaces, bordes, cabeceras, notas, error).
    "#9ebaff": "#2f5f9e",
    "#61728d": "#6f8579",
    "#52617b": "#bdcebf",
    "#3b4960": "#dbe3dc",
    "#becfed": "#40594f",
    "#c6cfdf": "#5b6f66",
    "#ffb4b4": "#a3282b",
}
PALETA_RGB = {
    (14, 20, 36): (250, 251, 247),
    (10, 14, 24): (250, 251, 247),
    (19, 28, 48): (250, 251, 247),
    (24, 34, 58): (255, 255, 255),
    (28, 39, 64): (255, 255, 255),
}
# Fondos que el template pinta con sus tokens oscuros (o con los «crema», que en el tema claro son la
# tinta): en el sistema claro son superficies tenues (el texto que llevaban encima, --cream, ya es
# tinta). Sólo como fondo: el mismo token como color de texto sigue siendo oscuro.
_RE_FONDO_OSCURO = re.compile(
    r"(background(?:-color)?\s*:\s*)var\(--(?:dark-teal|neutral-black|cream|cream-light|cream-pale)\)"
    r"(?=\s*[;}\"!]|\s*$)"
)
_RE_ESQUEMA_OSCURO = re.compile(r"color-scheme\s*:\s*dark\b")
# Barras pegajosas propias de la página: por debajo de la cabecera común (z-index 50 fija, 30 en la
# variante no fija) y de sus menús desplegables. Los valores por encima de 29 se comprimen a 21..29
# conservando el orden entre ellas (la barra del documento sigue por encima de la del visor).
Z_LOCAL_MAX = 29
ALTO_NAV_VIEJA = "64px"
# Alto de la barra fija vieja en escritorio y en móvil (``@media (max-width: 768px)``): las barras
# pegajosas que se colocaban justo debajo pasan a colocarse justo debajo de la cabecera común.
ALTOS_NAV_VIEJA = frozenset({"0", "0px", ALTO_NAV_VIEJA, "56px"})
_RE_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_RE_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*([,)])")
# Barra vieja: la de las páginas (`nav.nav#nav`) y la que emitían los generadores (`<nav>` con logo).
_RE_NAV_VIEJA = re.compile(
    r'[ \t]*<nav(?: class="nav" id="nav">|>\s*<a [^>]*class="logo")(?:(?!<nav\b).)*?</nav>[ \t]*\n?',
    re.S,
)
_RE_FUENTES = re.compile(
    r"[ \t]*<link[^>]+(?:fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>[ \t]*\n?", re.I
)
_RE_EDITORIAL_VIEJO = re.compile(
    r'[ \t]*<link rel="stylesheet" href="editorial\.css\?v=1">[ \t]*\n?'
)
_RE_SEL_NAV_VIEJA = re.compile(r"\.nav(?:-[\w-]+)?\b|#nav(?:Mobile)?\b|\.hamburger\b")
_RE_ELEMENTO = re.compile(r"(?<![\w.#:-])(nav|header|footer)(?![\w-])(?!:not\(\.site-)")
MARCA = "<!-- site:header:start -->"
_RE_CONTRADICTORIO = re.compile(
    r"(nav|header|footer):not\(\.site-\1\)(?:\.[\w-]+)*\.site-\1(?![\w-])"
)
# Enlace de salto viejo (cualquier orden de atributos): lo sustituye el del sistema común.
_RE_SALTO_VIEJO = re.compile(r'[ \t]*<a\b[^>]*\bclass="skip-link"[^>]*>.*?</a>\n?')


def mapea_colores(texto: str) -> str:
    """Traduce los literales de la paleta oscura a la clara (hex de 6 dígitos y rgb/rgba)."""
    texto = _RE_HEX.sub(lambda m: PALETA_HEX.get(m.group(0).lower(), m.group(0)), texto)

    def rgba(m: re.Match[str]) -> str:
        rgb = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if rgb not in PALETA_RGB:
            return m.group(0)
        r, g, b = PALETA_RGB[rgb]
        return m.group(0).split("(")[0] + f"({r},{g},{b}{m.group(4)}"

    texto = _RE_RGBA.sub(rgba, texto)
    texto = _RE_FONDO_OSCURO.sub(r"\g<1>var(--tint)", texto)
    return _RE_ESQUEMA_OSCURO.sub("color-scheme:light", texto)


def _fin_comentario(css: str, i: int) -> int:
    j = css.find("*/", i + 2)
    return len(css) if j < 0 else j + 2


def _fin_cadena(css: str, i: int) -> int:
    comilla, j = css[i], i + 1
    while j < len(css) and css[j] != comilla:
        j += 2 if css[j] == "\\" else 1
    return min(j + 1, len(css))


def _bloques(css: str) -> list[tuple[str, str]]:
    """Divide CSS en (prelude, cuerpo) de primer nivel.

    Espacios y comentarios van como piezas propias sin cuerpo (aunque haya espacio antes de
    ``/*``): así un comentario nunca queda pegado al selector o al ``@media`` que le sigue. Las
    llaves dentro de comentarios o cadenas no cuentan, y una regla-@ sin bloque (``@import …;``)
    termina en su ``;``.
    """
    out: list[tuple[str, str]] = []
    i, n = 0, len(css)
    while i < n:
        if css[i].isspace():
            j = i
            while j < n and css[j].isspace():
                j += 1
            out.append((css[i:j], ""))
            i = j
            continue
        if css.startswith("/*", i):
            j = _fin_comentario(css, i)
            out.append((css[i:j], ""))
            i = j
            continue
        j = i
        while j < n and css[j] not in "{;":
            if css.startswith("/*", j):
                j = _fin_comentario(css, j)
            elif css[j] in "\"'":
                j = _fin_cadena(css, j)
            else:
                j += 1
        if j >= n:
            out.append((css[i:], ""))
            break
        if css[j] == ";":
            out.append((css[i : j + 1], ""))
            i = j + 1
            continue
        prof, k = 1, j + 1
        while k < n and prof:
            if css.startswith("/*", k):
                k = _fin_comentario(css, k)
                continue
            if css[k] in "\"'":
                k = _fin_cadena(css, k)
                continue
            prof += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((css[i:j], css[j + 1 : k - 1]))
        i = k
    return out


def _selectores(prelude: str) -> list[str]:
    partes, prof, act = [], 0, ""
    for c in prelude:
        prof += {"(": 1, ")": -1}.get(c, 0)
        if c == "," and prof == 0:
            partes.append(act)
            act = ""
        else:
            act += c
    partes.append(act)
    return partes


_RE_PARTE_TABLA = re.compile(r"(?<![\w.#:-])(?:table|thead|tbody|tfoot|tr|th|td|caption)(?![\w-])")


def _pegajosos(css: str) -> frozenset[str]:
    """Selectores (fuera de tablas) que alguna regla del CSS hace ``position: sticky``."""
    sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    sel: set[str] = set()
    for m in re.finditer(r"([^{};]+)\{([^{}]*)\}", sin_comentarios):
        if re.search(r"position\s*:\s*sticky", m.group(2)):
            sel.update(s.strip() for s in _selectores(m.group(1)) if not _RE_PARTE_TABLA.search(s))
    return frozenset(sel)


def depura_css(css: str, pegajosos: frozenset[str] | None = None) -> str:
    """Retira reglas de la barra vieja y acota nav/header/footer para no alcanzar el chrome común."""
    if pegajosos is None:
        pegajosos = _pegajosos(css)
    salida = []
    for prelude, cuerpo in _bloques(css):
        cabeza = prelude.strip()
        if not cuerpo and (not cabeza.startswith("@") or cabeza.endswith(";")):
            # Espacio, comentario o regla-@ sin bloque: tal cual. Una regla vacía se retira.
            conserva = not cabeza or cabeza.startswith(("/*", "@"))
            salida.append(prelude if conserva else "")
            continue
        if cabeza.startswith("@media") or cabeza.startswith("@supports"):
            salida.append(f"{prelude}{{{depura_css(cuerpo, pegajosos)}}}")
            continue
        if cabeza.startswith("@"):
            salida.append(f"{prelude}{{{cuerpo}}}")
            continue
        selectores = _selectores(re.sub(r"/\*.*?\*/", "", prelude, flags=re.S))
        quedan = [s for s in selectores if not _RE_SEL_NAV_VIEJA.search(s)]
        if not quedan:
            continue
        acotados = [
            _fuera_del_chrome(
                _RE_ELEMENTO.sub(lambda m: f"{m.group(1)}:not(.site-{m.group(1)})", s)
            )
            for s in quedan
        ]
        # `footer.site-footer` del template era SU pie (ahora colofón o retirado): acotado queda
        # `footer:not(.site-footer).site-footer`, que nunca coincide. Fuera, en vez de dejarlo muerto.
        acotados = [s for s in acotados if not _RE_CONTRADICTORIO.search(s)]
        if not acotados:
            continue
        salida.append(f"{','.join(acotados)}{{{_ajusta_cuerpo(quedan, cuerpo, pegajosos)}}}")
    return "".join(salida)


_RE_PSEUDO_ELEMENTO = re.compile(
    r"::?(?:before|after|first-line|first-letter|marker|placeholder|selection)\b.*$"
)
CHROME = ":not(:where(.site-header, .site-footer) *)"


def _fuera_del_chrome(selector: str) -> str:
    """Un selector sólo de tipos (``a``, ``p``, ``a:hover``, ``ul li``, ``*``…) de la hoja de una
    página alcanzaría también la cabecera y el pie comunes (p. ej. ``a { color: … !important }``).
    Se le añade ``:not(:where(.site-header, .site-footer) *)``: misma especificidad (``:where``
    vale 0), mismo efecto en el contenido, ninguno en el chrome. Los que ya llevan clase, id o
    atributo no se tocan (idempotente), ni ``html``/``body``/``:root``."""
    sel = selector.strip()
    if not sel or any(c in sel for c in ".#[") or sel.startswith(":"):
        return selector
    ultimo = re.split(r"[\s>+~]+", sel)[-1]
    base = re.match(r"[A-Za-z][\w-]*|\*", ultimo)
    if not base or base.group(0).lower() in {"html", "body"}:
        return selector
    pseudo = _RE_PSEUDO_ELEMENTO.search(sel)
    corte = pseudo.start() if pseudo else len(sel)
    inicio = selector[: len(selector) - len(selector.lstrip())]
    final = selector[len(inicio) + len(sel) :]
    return f"{inicio}{sel[:corte]}{CHROME}{sel[corte:]}{final}"


def _z_local(z: int) -> int:
    # Ya por debajo de la cabecera (≤ 29): tal cual, así la segunda pasada no cambia nada.
    return z if z <= Z_LOCAL_MAX else min(Z_LOCAL_MAX, 20 + z // 50)


def _ajusta_cuerpo(selectores: list[str], cuerpo: str, pegajosos: frozenset[str]) -> str:
    """Compensaciones de la barra fija vieja y capas/posición de las barras pegajosas propias.

    Una barra pegajosa de la página (no una cabecera de tabla, que se pega dentro de su contenedor
    con scroll) se coloca debajo de la cabecera común: ``top: X`` pasa a
    ``calc(var(--site-header-h, 0px) + X)`` en todas sus reglas, también las de ``@media``. ``0`` y
    el alto de la barra fija vieja (64 px; 56 px en móvil) pasan a ``var(--site-header-h, 0px)``.
    """
    if any(s.strip() == "body" for s in selectores):
        cuerpo = re.sub(
            r"\s*padding-top\s*:\s*" + ALTO_NAV_VIEJA + r"\s*(?:;|(?=\s*$))", "", cuerpo
        )
    if re.search(r"position\s*:\s*sticky", cuerpo):
        cuerpo = re.sub(
            r"(z-index\s*:\s*)(\d+)",
            lambda m: m.group(1) + str(_z_local(int(m.group(2)))),
            cuerpo,
        )
    if any(s.strip() in pegajosos for s in selectores):

        def bajo_cabecera(m: re.Match[str]) -> str:
            valor = m.group(2)
            if valor in ALTOS_NAV_VIEJA:
                return m.group(1) + "var(--site-header-h, 0px)"
            return m.group(1) + f"calc(var(--site-header-h, 0px) + {valor})"

        cuerpo = re.sub(
            r"((?<![\w-])top\s*:\s*)(-?\d+(?:\.\d+)?(?:px|rem|em)?)(?![\w.%(])",
            bajo_cabecera,
            cuerpo,
        )
    return cuerpo


def _transforma_estilos(html: str) -> str:
    html = re.sub(
        r"(<style[^>]*>)(.*?)(</style>)",
        lambda m: m.group(1) + depura_css(mapea_colores(m.group(2))) + m.group(3),
        html,
        flags=re.S,
    )
    html = re.sub(
        r'(\sstyle=")([^"]*)(")',
        lambda m: m.group(1)
        + _grid_responsiva(_texto_legible(mapea_colores(m.group(2))))
        + m.group(3),
        html,
    )
    return re.sub(
        r"(<script(?:\s[^>]*)?>)(.*?)(</script>)",
        lambda m: m.group(1) + mapea_colores(m.group(2)) + m.group(3),
        html,
        flags=re.S,
    )


def _luminancia(hexa: str) -> float:
    canales = [int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


TINTA_SOBRE_COLOR = "#0b0f1a"
_RE_GRID_FIJA = re.compile(
    r"grid-template-columns\s*:\s*(?:repeat\(\s*([2-6])\s*,\s*1fr\s*\)|((?:1fr\s*){2,6}))(?=\s*(?:;|$))"
)
COLUMNA_MIN = "12rem"


def _grid_responsiva(estilo: str) -> str:
    """Rejilla en línea de N columnas iguales (``1fr 1fr``, ``repeat(3, 1fr)``): con el mismo número
    de columnas cuando caben (cada una ≥ ``COLUMNA_MIN``) y menos en pantallas estrechas, en vez de
    columnas de 25 px a 360 px. Una hoja no puede cambiar un estilo en línea sin ``!important``."""
    if "display:grid" not in estilo.replace(" ", ""):
        return estilo

    def responsiva(m: re.Match[str]) -> str:
        n = int(m.group(1)) if m.group(1) else len(m.group(2).split())
        hueco = re.search(r"(?<![\w-])(?:column-)?gap\s*:\s*([\d.]+(?:rem|px|em))", estilo)
        resto = f"(100% - {n - 1} * {hueco.group(1)}) / {n}" if hueco else f"100% / {n}"
        return (
            "grid-template-columns:repeat(auto-fit,minmax(min(100%,"
            f"max({COLUMNA_MIN},{resto})),1fr))"
        )

    return _RE_GRID_FIJA.sub(responsiva, estilo)


def _texto_legible(estilo: str) -> str:
    """Insignia en línea con texto blanco sobre un color propio (p. ej. el naranja del ensemble en
    validación semanal, ratio 2.79): si el blanco no llega a 4.5:1 y la tinta oscura sí, el texto
    pasa a tinta. El fondo, que identifica al modelo o al estado, no cambia."""
    fondo = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6})\b", estilo)
    texto = re.search(r"(?<![\w-])color\s*:\s*(#fff(?:fff)?|white)\b", estilo, re.I)
    if not fondo or not texto:
        return estilo
    if _contraste("#ffffff", fondo.group(1)) >= 4.5:
        return estilo
    if _contraste(TINTA_SOBRE_COLOR, fondo.group(1)) < 4.5:
        return estilo
    return estilo[: texto.start(1)] + TINTA_SOBRE_COLOR + estilo[texto.end(1) :]


def _version(fragmentos: dict[str, Any] | None, ruta: str) -> str:
    assets = (fragmentos or {}).get("assets") or {}
    v = assets.get(ruta)
    return f"{ruta}?v={v}" if v else ruta


def _sincroniza_versiones(html: str, fragmentos: dict[str, Any] | None) -> str:
    """``?v=`` de los recursos comunes igual al manifiesto del frontend (una plantilla migrada sin
    fragmentos los lleva sin versión; la versión la decide el dashboard, no el backend)."""
    for ruta in (fragmentos or {}).get("assets") or {}:
        patron = re.compile(r'((?:href|src)=")' + re.escape(ruta) + r'(?:\?v=[^"]*)?"')
        versionada = _version(fragmentos, ruta)
        html = patron.sub(r"\g<1>" + versionada.replace("\\", "\\\\") + '"', html)
    return html


def _quita_div(html: str, inicio: int) -> str:
    """Quita el <div …> que empieza en `inicio` con su contenido, contando anidamiento."""
    prof = 0
    for m in re.finditer(r"<(/?)div\b[^>]*>", html[inicio:]):
        prof += -1 if m.group(1) else 1
        if prof == 0:
            fin = inicio + m.end()
            return html[:inicio] + html[fin:].lstrip("\n")
    raise ValueError("div sin cierre")


def _body_editorial(m: re.Match[str]) -> str:
    attrs = m.group(1)
    if 'class="' in attrs:
        return "<body" + attrs.replace('class="', 'class="editorial-page ', 1) + ">"
    return f'<body{attrs} class="editorial-page">'


def adapta(
    html: str,
    fragmentos: dict[str, Any] | None = None,
    familia: str = "editorial",
    *,
    colofon: bool = True,
    salto: str = "contenido",
) -> str:
    """Página editorial vieja -> sistema común. Con ``fragmentos``, además estampa el shell.

    ``salto``: id que recibe el primer bloque de contenido si no tiene uno (destino del enlace de
    salto). En la familia ``noticias`` la cabecera real del archivo conserva además el alias
    histórico ``#hero``.
    """
    if MARCA in html:
        # Ya migrada (o plantilla migrada): sólo la paleta de lo que el generador inyectó y el
        # estampado. Sobre una página ya adaptada es un no-op salvo el chrome.
        html = _envuelve_tablas(_transforma_estilos(_RE_SALTO_VIEJO.sub("", html, count=1)))
        if familia == "noticias":
            html = _ancla_hero(html)
        if not fragmentos:
            return html
        return estampa(_sincroniza_versiones(html, fragmentos), familia, fragmentos)
    head_fin = html.index("</head>")
    cabeza = _RE_FUENTES.sub("", html[:head_fin])
    cabeza = re.sub(r'[ \t]*<link rel="preconnect"[^>]*>[ \t]*\n?', "", cabeza)
    cabeza = _RE_EDITORIAL_VIEJO.sub("", cabeza)
    enlaces = (
        f'<link rel="stylesheet" href="{_version(fragmentos, "assets/site/site.css")}">\n'
        f'<link rel="stylesheet" href="{_version(fragmentos, "editorial.css")}">\n'
    )
    html = cabeza + enlaces + html[head_fin:]
    html = re.sub(r"<body([^>]*)>", _body_editorial, html, count=1)
    marcadores = "<!-- site:header:start -->\n<!-- site:header:end -->\n"
    nav = _RE_NAV_VIEJA.search(html)
    if nav:
        html = html[: nav.start()] + marcadores + html[nav.end() :]
    else:
        cuerpo = re.search(r"<body[^>]*>\n?", html)
        assert cuerpo is not None
        html = html[: cuerpo.end()] + marcadores + html[cuerpo.end() :]
    movil = re.search(r'[ \t]*<div class="nav-mobile"[^>]*id="navMobile"', html)
    if movil:
        html = _quita_div(html, movil.start())
    html = _RE_SALTO_VIEJO.sub("", html, count=1)
    html = html.replace(
        marcadores, '<a class="skip" href="#contenido">Saltar al contenido</a>\n' + marcadores, 1
    )
    # Destino del salto: el primer bloque de contenido tras la cabecera.
    i = html.index("<!-- site:header:end -->")
    bloque = re.compile(r"<(section|header|main|div)\b([^>]*)>").search(html, i)
    if bloque and " id=" not in bloque.group(2):
        html = (
            html[: bloque.start()]
            + f'<{bloque.group(1)} id="{salto}"{bloque.group(2)}>'
            + html[bloque.end() :]
        )
        html = html.replace('href="#contenido"', f'href="#{salto}"', 1)
    elif bloque:
        destino = re.search(r'\sid="([^"]+)"', bloque.group(2))
        if destino:
            html = html.replace('href="#contenido"', f'href="#{destino.group(1)}"', 1)
    pie = re.search(r"<footer\b([^>]*)>(.*?)</footer>", html, re.S)
    marcas_pie = "<!-- site:footer:start -->\n<!-- site:footer:end -->"
    if pie and not colofon:
        html = html[: pie.start()] + marcas_pie + html[pie.end() :]
    elif pie:
        # El colofón deja de ser un pie: sin las clases que el chrome común usa para el suyo.
        def _clases(m: re.Match[str]) -> str:
            resto = [c for c in m.group(1).split() if c not in {"site-footer", "footer"}]
            return 'class="' + " ".join(["legacy-colophon", *resto]) + '"'

        clase = (
            re.sub(r'class="([^"]*)"', _clases, pie.group(1))
            if "class=" in pie.group(1)
            else ' class="legacy-colophon"' + pie.group(1)
        )
        html = (
            html[: pie.start()]
            + f"<div{clase}>{pie.group(2)}</div>\n{marcas_pie}"
            + html[pie.end() :]
        )
    else:
        guion = re.search(r"\n[ \t]*<script", html[html.index("<!-- site:header:end -->") :])
        corte = (
            html.index("<!-- site:header:end -->") + guion.start()
            if guion
            else html.rindex("</body>")
        )
        html = html[:corte] + f"\n{marcas_pie}" + html[corte:]
    html = _envuelve_tablas(_transforma_estilos(html))
    if familia == "noticias":
        html = _ancla_hero(html)
    html = html.replace(
        "</body>",
        f'<script src="{_version(fragmentos, "assets/site/site-nav.js")}"></script>\n</body>',
        1,
    )
    return estampa(html, familia, fragmentos) if fragmentos else html


_RE_PROTEGIDO = re.compile(r"<(script|style|template|textarea)\b.*?</\1\s*>", re.S | re.I)
_RE_ENVOLTORIO = re.compile(r'<div\b[^>]*\bclass="[^"]*(?:table|tabla|scroll)[^"]*"[^>]*>$')
ENVOLTORIO_TABLA = '<div class="tabla-desplazable">'


def _envuelve_tablas(html: str) -> str:
    """Una tabla del contenido sin contenedor propio de desplazamiento queda envuelta en
    ``div.tabla-desplazable`` (``editorial.css``: ``overflow-x: auto``): a 360 px o con texto al
    200 % se desplaza la tabla, no la página. No toca tablas dentro de ``<script>``/``<style>``, ni
    las que ya tienen un contenedor (``.table-wrap``, ``.table-scroll``…): idempotente."""
    salida, i = [], 0
    for m in [*_RE_PROTEGIDO.finditer(html), None]:
        fin = m.start() if m else len(html)
        salida.append(_envuelve_tramo(html[i:fin]))
        if m:
            salida.append(m.group(0))
            i = m.end()
    return "".join(salida)


def _envuelve_tramo(tramo: str) -> str:
    out, i = [], 0
    while True:
        a = re.search(r"<table\b", tramo[i:], re.I)
        if not a:
            out.append(tramo[i:])
            return "".join(out)
        ini = i + a.start()
        prof, fin = 0, None
        for t in re.finditer(r"<(/?)table\b[^>]*>", tramo[ini:], re.I):
            prof += -1 if t.group(1) else 1
            if prof == 0:
                fin = ini + t.end()
                break
        if fin is None:
            out.append(tramo[i:])
            return "".join(out)
        previo = tramo[:ini].rstrip()
        out.append(tramo[i:ini])
        if _RE_ENVOLTORIO.search(previo[-400:]):
            out.append(tramo[ini:fin])
        else:
            out.append(ENVOLTORIO_TABLA + tramo[ini:fin] + "</div>")
        i = fin


def _ancla_hero(html: str) -> str:
    """``novedades.html#hero``: alias histórico (el pie viejo lo enlazaba) hacia la cabecera real
    del archivo (fecha de edición, título y entradilla), sin quitarle ``#archivo`` a la sección."""
    if 'id="hero"' in html:
        return html
    cabecera = re.search(r'(<section\b[^>]*\bid="archivo"[^>]*>\s*<div\b)(?![^>]*\sid=)', html)
    if not cabecera:
        raise ValueError(
            "noticias: no se encontró la cabecera del archivo (section#archivo > div)"
        )
    return html[: cabecera.end()] + ' id="hero"' + html[cabecera.end() :]


DASHBOARD_ENV = "EPIFORECAST_DASHBOARD"


def publica_editorial(
    html: str,
    dashboard: Path | None = None,
    *,
    familia: str = "editorial",
    colofon: bool = True,
    exigir: bool = False,
) -> str:
    """Lo que llama un generador del backend antes de escribir una página editorial.

    ``dashboard``: el recibido; si no, ``$EPIFORECAST_DASHBOARD`` (el staging del refresh semanal).
    Con fragmentos (``assets/site/shell.fragments.json``) la página sale con el chrome común
    estampado, igual que ``site_shell.mjs``. Falla cerrado (:class:`ShellError`) si se exige —el
    generador escribe directamente en un dashboard— o si la variable de entorno apunta a un
    dashboard sin fragmentos. Sin dashboard alguno (copia local del backend) sale adaptada con los
    marcadores vacíos: ``site_shell.mjs --check`` no la daría por buena si llegara al sitio sin
    estampar.
    """
    desde_entorno = dashboard is None and bool(os.environ.get(DASHBOARD_ENV))
    if dashboard is None and desde_entorno:
        dashboard = Path(os.environ[DASHBOARD_ENV])
    fragmentos = None
    if dashboard is not None and (Path(dashboard) / FRAGMENTOS).is_file():
        fragmentos = cargar_fragmentos(Path(dashboard))
    elif dashboard is not None and (exigir or desde_entorno):
        raise ShellError(
            f"{Path(dashboard) / FRAGMENTOS} no existe: la página no puede salir sin el chrome común"
        )
    elif exigir:
        raise ShellError("se exige el chrome común y no se recibió dashboard")
    else:
        print(
            "aviso: sin dashboard con fragmentos; la página queda con marcadores vacíos",
            file=sys.stderr,
        )
    return adapta(html, fragmentos, familia, colofon=colofon)
