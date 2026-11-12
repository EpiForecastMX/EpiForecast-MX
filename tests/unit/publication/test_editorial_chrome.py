"""Transformador de páginas editoriales al sistema visual común y su uso en los generadores.

Corre siempre: los fragmentos reales vienen del fixture ``tests/fixtures/site_shell`` (copia literal
del frontend), no del repositorio hermano.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from epiforecast.publication.editorial_chrome import (
    adapta,
    depura_css,
    mapea_colores,
    publica_editorial,
)
from epiforecast.publication.site_shell import ShellError, cargar_fragmentos

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "site_shell"
FRAG = cargar_fragmentos(FIXTURE)

# Página con la plantilla vieja: barra `nav.nav#nav` + menú móvil, fuentes externas, editorial.css
# v1, pie propio y la paleta oscura en <style>, en `style=""` y en un <script>.
VIEJA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Prueba</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
body{background:#0e1424;color:#e7ecf5}
.nav{position:fixed;top:0}
.nav-menu a,.card{color:#9fb0ce}
nav a{color:red}
footer{border-top:1px solid #243150}
@media (max-width:600px){.hamburger{display:block}.card{padding:1rem}}
</style>
<link rel="stylesheet" href="editorial.css?v=1">
</head>
<body>
<nav class="nav" id="nav"><div class="nav-inner"><a class="nav-logo" href="index.html">EF</a></div></nav>
<div class="nav-mobile" id="navMobile"><div><a href="index.html">Inicio</a></div></div>
<section class="hero"><h1>Título</h1><p style="color:#6e82a6">53.2 sMAPE · 0.387 MASE</p></section>
<div class="card">267 de 288 · 333 modelos</div>
<footer class="pie"><p class="footer-title">EpiForecast-MX</p><p>Generado: 01/11/2026</p></footer>
<script>var c="#2dd4bf";var fondo="rgba(14,20,36,0.9)";</script>
</body>
</html>
"""


def _texto(html: str) -> str:
    sin = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    sin = re.sub(
        r"<!-- site:(header|footer):start -->.*?<!-- site:\1:end -->", " ", sin, flags=re.S
    )
    return " ".join(re.sub(r"<[^>]+>", " ", sin).split())


def test_quita_el_chrome_viejo_y_deja_marcadores_estampados() -> None:
    sin_estampar = adapta(VIEJA, None, colofon=False)
    assert '<nav class="nav" id="nav">' not in sin_estampar and "navMobile" not in sin_estampar
    nueva = adapta(VIEJA, FRAG, colofon=False)
    assert nueva.count('<nav class="nav" id="nav">') == 0
    assert "fonts.googleapis" not in nueva and "editorial.css?v=1" not in nueva
    assert nueva.count('<header class="site-header" id="nav" lang="es">') == 1
    assert nueva.count('<footer class="site-footer" lang="es">') == 1
    assert '<footer class="pie"' not in nueva and "legacy-colophon" not in nueva
    v = FRAG["assets"]
    assert f'href="assets/site/site.css?v={v["assets/site/site.css"]}"' in nueva
    assert f'href="editorial.css?v={v["editorial.css"]}"' in nueva
    assert f'src="assets/site/site-nav.js?v={v["assets/site/site-nav.js"]}"' in nueva
    # site.css antes que editorial.css, ambos después del <style> en línea.
    assert (
        nueva.index("</style>")
        < nueva.index("assets/site/site.css")
        < nueva.index('href="editorial.css')
    )
    assert '<body class="editorial-page">' in nueva
    assert '<a class="skip" href="#contenido">' in nueva
    assert '<section id="contenido" class="hero">' in nueva


def test_conserva_el_contenido_y_las_cifras() -> None:
    nueva = adapta(VIEJA, FRAG, colofon=True)
    # Todo el texto de la página sigue (el pie como colofón); sólo cambia el chrome.
    esperado = _texto(VIEJA).replace("EF ", "").replace("Inicio ", "")
    assert _texto(nueva) == esperado.replace("Prueba ", "Prueba Saltar al contenido ")
    for cifra in ("53.2 sMAPE", "0.387 MASE", "267 de 288", "333 modelos", "01/11/2026"):
        assert cifra in nueva
    assert '<div class="legacy-colophon pie"><p class="footer-title">' in nueva


def test_paleta_clara_y_selectores_acotados() -> None:
    nueva = adapta(VIEJA, FRAG)
    for oscuro in ("#0e1424", "#e7ecf5", "#9fb0ce", "#243150", "#6e82a6", "#2dd4bf", "14,20,36"):
        assert oscuro not in nueva.lower(), oscuro
    css = re.search(r"<style>(.*?)</style>", nueva, re.S).group(1)  # type: ignore[union-attr]
    assert ".nav{" not in css and ".nav-menu" not in css and ".hamburger" not in css
    assert ".card{color:#40594f}" in css  # el selector compartido sobrevive sin el de la barra
    assert "nav:not(.site-nav) a{color:red}" in css
    assert "footer:not(.site-footer){" in css
    assert "@media (max-width:600px){.card{padding:1rem}}" in css


def test_idempotente_y_no_op_sobre_una_pagina_ya_migrada() -> None:
    una = adapta(VIEJA, FRAG)
    assert adapta(una, FRAG) == una
    assert depura_css(depura_css("nav a{x:1}")) == depura_css("nav a{x:1}")
    assert mapea_colores(mapea_colores("#0E1424")) == "#fafbf7"


def test_la_pagina_real_del_frontend_es_el_resultado_del_algoritmo() -> None:
    """reporte_resultados.html (fixture del frontend): re-adaptarla con sus fragmentos no cambia
    un byte, y vaciar su chrome y re-estamparlo la reproduce."""
    real = (FIXTURE / "reporte_resultados.html").read_text(encoding="utf-8")
    assert adapta(real, FRAG) == real
    vacia = re.sub(
        r"<!-- site:(header|footer):start -->.*?<!-- site:\1:end -->",
        lambda m: f"<!-- site:{m.group(1)}:start -->\n<!-- site:{m.group(1)}:end -->",
        real,
        flags=re.S,
    )
    sin_version = re.sub(
        r"(assets/site/site\.css|editorial\.css|site-nav\.js)\?v=\w+", r"\1", vacia
    )
    assert adapta(sin_version, FRAG) == real


def test_plantilla_migrada_traduce_lo_inyectado_y_toma_las_versiones(tmp_path: Path) -> None:
    plantilla = adapta(VIEJA.replace("267 de 288", "__TOKEN__"), None)
    assert (
        "?v=" not in plantilla
        and "<!-- site:header:start -->\n<!-- site:header:end -->" in plantilla
    )
    html = plantilla.replace("__TOKEN__", '<span style="color:#F472B6">x</span>')
    final = publica_editorial(html, FIXTURE, exigir=True)
    assert "#a3367a" in final and "#F472B6" not in final
    assert f'site.css?v={FRAG["assets"]["assets/site/site.css"]}"' in final
    assert publica_editorial(final, FIXTURE, exigir=True) == final


def test_publica_falla_cerrado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EPIFORECAST_DASHBOARD", raising=False)
    with pytest.raises(ShellError):
        publica_editorial(VIEJA, tmp_path, exigir=True)
    with pytest.raises(ShellError):
        publica_editorial(VIEJA, exigir=True)
    monkeypatch.setenv("EPIFORECAST_DASHBOARD", str(tmp_path))
    with pytest.raises(ShellError, match="shell.fragments.json"):
        publica_editorial(VIEJA)
    monkeypatch.setenv("EPIFORECAST_DASHBOARD", str(FIXTURE))
    assert 'class="site-header"' in publica_editorial(VIEJA)
    monkeypatch.delenv("EPIFORECAST_DASHBOARD")
    local = publica_editorial(VIEJA)  # copia local del backend: adaptada, marcadores vacíos
    assert "<!-- site:header:start -->\n<!-- site:header:end -->" in local
    assert '<nav class="nav" id="nav">' not in local


# --- Generadores reales ---------------------------------------------------------------------


def test_genera_reporte_con_la_plantilla_real(tmp_path: Path) -> None:
    from scripts import genera_reporte as gr

    from tests.unit.test_reporte_sin_metricas_seleccion import _dengue, _stats

    html = publica_editorial(gr.build_html(_stats(), _dengue()), FIXTURE, exigir=True)
    assert '<nav class="nav" id="nav">' not in html and "fonts.googleapis" not in html
    assert html.count('<header class="site-header" id="nav" lang="es">') == 1
    assert "legacy-colophon" in html  # página del corpus del EpiBot
    assert not re.search(r"__[A-Z_]+__", html)
    plantilla = gr.TEMPLATE.read_text(encoding="utf-8")
    assert '<nav class="nav" id="nav">' not in plantilla and "fonts.googleapis" not in plantilla
    assert "<!-- site:header:start -->\n<!-- site:header:end -->" in plantilla


def test_genera_bitacora_escribe_donde_se_le_dice_con_el_chrome(tmp_path: Path) -> None:
    from scripts import genera_bitacora as gb

    destino = tmp_path / "bitacora_modelado.html"
    gb.main(["--out", str(destino), "--dashboard", str(FIXTURE)])
    html = destino.read_text(encoding="utf-8")
    assert "<nav>" not in html and "fonts.googleapis" not in html
    assert html.count('<header class="site-header" id="nav" lang="es">') == 1
    assert "legacy-colophon" in html
    previo = html
    gb.main(["--out", str(destino), "--dashboard", str(FIXTURE)])
    fecha = re.compile(r"Generado el [^&]+")
    assert fecha.sub("", destino.read_text(encoding="utf-8")) == fecha.sub("", previo)


def test_genera_validacion_semanal_real_con_el_chrome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import genera_validacion_semanal as gv

    monkeypatch.delenv("EPIFORECAST_DASHBOARD", raising=False)
    monkeypatch.setattr(gv, "_update_excel", lambda *a, **k: 0)
    monkeypatch.setattr(gv, "_destino_excel", lambda out: out / "x.xlsx")
    seg = Path("reports/ProdDetails/seguimiento_post_corte.csv")
    gv.main(["--out", str(tmp_path), "--seguimiento", str(seg), "--dashboard", str(FIXTURE)])
    html = (tmp_path / "validacion_semanal.html").read_text(encoding="utf-8")
    assert html.count('<header class="site-header" id="nav" lang="es">') == 1
    assert "fonts.googleapis" not in html and "editorial.css?v=1" not in html
    assert '<div class="legacy-colophon"' in html
    assert gv._normaliza_para_hooks(html) == html  # los hooks no tienen nada que cambiar


def test_comparison_report_real_con_csv_de_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from epiforecast.visualization import comparison_report as cr
    from epiforecast.visualization.comparison_html import _MODELS

    monkeypatch.setenv("EPIFORECAST_DASHBOARD", str(FIXTURE))
    monkeypatch.chdir(tmp_path)
    for i, modelo in enumerate(list(_MODELS)[:2]):
        carpeta = tmp_path / "models" / modelo
        carpeta.mkdir(parents=True)
        (carpeta / "alzheimer_completo.csv").write_text(
            "padecimiento,sexo,nivel,Entidad,rmse,mae,smape,mase\n"
            f"Alzheimer,general,nacional,,1.0,0.5,{20 + i},0.9\n",
            encoding="utf-8",
        )
    salida = cr.generar_reporte_html({"paths": {"reports": str(tmp_path / "reports")}})
    assert salida is not None
    html = salida.read_text(encoding="utf-8")
    assert html.count('<header class="site-header" id="nav" lang="es">') == 1
    assert "fonts.googleapis" not in html and "editorial.css?v=1" not in html
    assert '<body class="editorial-page">' in html or 'class="editorial-page' in html


# --- Correcciones de la auditoría de todas las páginas ---------------------------------------

# CSS real de auditoria_remediacion_2026.html / Avance1.Equipo01.html (HEAD), con los casos que
# rompían el parser: comentario precedido de espacio, @media tras comentario y llaves en comentarios
# o cadenas.
CSS_REAL = """
  body {
    font-family: var(--font-body);
    padding-top: 64px;
    -webkit-font-smoothing: antialiased;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .container { padding: 1rem; }
    header h1 { font-size: 1.4rem; }
    .nav { display: none; }
  }
  @media print { .nav { display: none; } }

  /* Site footer */
  footer.site-footer {
    background: var(--bg-deep);
  }
  footer.site-footer a { color: var(--text-muted); }
  /* .nav vieja: el comentario no se lleva la regla siguiente */
  .card { color: red; }
  .q::before { content: "}"; }
  /* { */ .r { x: 1; }
  @import url("x.css");
  .s { y: 2; }
"""


def test_parser_css_con_comentarios_media_y_cadenas_reales() -> None:
    css = depura_css(CSS_REAL)
    assert "/* Responsive */" in css and "/* Site footer */" in css  # comentarios intactos
    assert "footer:not" not in css.split("/* Site footer */")[0].split("@media")[0]
    # El @media precedido de comentario se recorre: header acotado, barra vieja fuera.
    media = css[css.index("@media (max-width: 768px)") :].split("@media print")[0]
    assert "header:not(.site-header) h1" in media and ".nav" not in media
    assert "@media print {" in css and ".nav" not in css.split("@media print")[1].split("}")[0]
    # El pie propio del template (footer.site-footer) ya no existe: sus reglas se retiran en vez
    # de quedar como `footer:not(.site-footer).site-footer`, que nunca coincide.
    assert ".site-footer" not in css.replace(":not(:where(.site-header, .site-footer) *)", "")
    assert ".card { color: red; }" in css  # el comentario con «.nav» no se lleva la regla
    assert '.q::before { content: "}"; }' in css and ".r { x: 1; }" in css
    assert '@import url("x.css");' in css and ".s { y: 2; }" in css
    assert depura_css(css) == css


def test_compensaciones_de_la_barra_vieja_y_barras_pegajosas_bajo_la_cabecera() -> None:
    css = depura_css(
        "body{padding-top:64px;color:#111}"
        "header{position:sticky;top:0;z-index:100}"
        ".toolbar{position:sticky;top:54px;z-index:90}"
        "@media (max-width:520px){.toolbar{top:48px;padding-top:6px}}"
        ".section-nav{position:sticky;top:64px;z-index:900}"
        "@media (max-width:768px){.section-nav{top:56px}}"
        "thead th{position:sticky;top:0;z-index:2}"
        ".lightbox{position:fixed;top:0;z-index:1000}"
    )
    assert "body{color:#111}" in css  # sin el hueco de 64 px de la barra fija vieja
    assert (
        "header:not(.site-header){position:sticky;top:var(--site-header-h, 0px);z-index:22}" in css
    )
    assert ".toolbar{position:sticky;top:calc(var(--site-header-h, 0px) + 54px);z-index:21}" in css
    assert ".toolbar{top:calc(var(--site-header-h, 0px) + 48px);padding-top:6px}" in css
    assert ".section-nav{position:sticky;top:var(--site-header-h, 0px);z-index:29}" in css
    assert ".section-nav{top:var(--site-header-h, 0px)}" in css
    # Las cabeceras de tabla se pegan dentro de su contenedor: ni top ni z-index cambian; un
    # modal fijo sigue por encima de todo.
    assert (
        "thead th:not(:where(.site-header, .site-footer) *){position:sticky;top:0;z-index:2}"
        in css
    )
    assert ".lightbox{position:fixed;top:0;z-index:1000}" in css
    assert depura_css(css) == css


def test_colofon_sin_clases_de_pie_y_salto_viejo_fuera() -> None:
    vieja = VIEJA.replace('<footer class="pie">', '<footer class="site-footer pie">').replace(
        "<body>", '<body>\n<a href="#main" class="skip-link">Saltar</a>'
    )
    nueva = adapta(vieja, FRAG, colofon=True)
    assert '<div class="legacy-colophon pie">' in nueva
    assert nueva.count('class="site-footer"') == 1  # sólo el pie común
    assert "skip-link" not in nueva and nueva.count('class="skip"') == 1
    assert adapta(nueva, FRAG) == nueva


NOTICIAS = """<!DOCTYPE html><html lang="es"><head><title>N</title></head><body>
<nav class="nav" id="nav"><a href="index.html">EF</a></nav>
<main id="main">
<section class="edl-hero" id="archivo">
<div class="edl-wrap"><h1 class="edl-headline">Novedades</h1></div>
<div class="arch-list" id="newsGrid"></div>
</section></main>
<footer class="pie"><a href="#hero">Inicio</a></footer>
</body></html>
"""


def test_noticias_conserva_el_alias_hero_en_la_cabecera_del_archivo() -> None:
    nueva = adapta(NOTICIAS, FRAG, "noticias", colofon=False)
    assert '<section class="edl-hero" id="archivo">\n<div id="hero" class="edl-wrap">' in nueva
    assert nueva.count('id="hero"') == 1 and 'href="#hero"' not in nueva  # el pie viejo se fue
    assert adapta(nueva, FRAG, "noticias") == nueva
    assert 'id="hero"' not in adapta(NOTICIAS, FRAG, "editorial", colofon=False)


def test_tablas_sueltas_se_desplazan_en_su_contenedor() -> None:
    html = VIEJA.replace(
        '<div class="card">',
        "<table><tr><td>a</td></tr></table>\n"
        '<div class="table-wrap"><table><tr><td>b</td></tr></table></div>\n'
        "<script>var t='<table></table>';</script>\n"
        '<div class="card">',
    )
    nueva = adapta(html, FRAG)
    assert '<div class="tabla-desplazable"><table><tr><td>a</td></tr></table></div>' in nueva
    assert '<div class="table-wrap"><table>' in nueva and nueva.count("tabla-desplazable") == 1
    assert "var t='<table></table>'" in nueva
    assert adapta(nueva, FRAG) == nueva


def test_selectores_de_tipo_no_alcanzan_la_cabecera_ni_el_pie() -> None:
    css = depura_css(
        "*{margin:0}a{color:red!important}a:hover::after{x:1}p,.x a{y:2}"
        "body{z:3}html{w:4}:root{--a:1}ul li{v:5}"
    )
    no = ":not(:where(.site-header, .site-footer) *)"
    assert f"*{no}{{margin:0}}" in css
    assert f"a{no}{{color:red!important}}" in css
    assert f"a:hover{no}::after{{x:1}}" in css
    assert f"p{no},.x a{{y:2}}" in css  # con clase no alcanza el chrome: intacto
    assert "body{z:3}" in css and "html{w:4}" in css and ":root{--a:1}" in css
    assert f"ul li{no}{{v:5}}" in css
    assert depura_css(css) == css


def test_insignias_en_linea_con_texto_legible_y_rejillas_que_se_pliegan() -> None:
    html = VIEJA.replace(
        '<div class="card">',
        '<span style="color:#fff;background:#FF6F00">Ensemble</span>'
        '<span style="color:#fff;background:#1A237E">Stacking</span>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem">x</div>'
        '<div style="display:grid;grid-template-columns:repeat(3, 1fr)">y</div>'
        '<div style="display:grid;grid-template-columns:120px 1fr">z</div>'
        '<div class="card">',
    )
    nueva = adapta(html, FRAG)
    # El naranja del ensemble (identidad del modelo) se queda; el texto pasa a tinta (2.79 -> 7+).
    assert 'style="color:#0b0f1a;background:#FF6F00">Ensemble' in nueva
    assert 'style="color:#fff;background:#1A237E">Stacking' in nueva  # ya era AA
    assert (
        "grid-template-columns:repeat(auto-fit,minmax(min(100%,max(12rem,"
        "(100% - 1 * 2rem) / 2)),1fr))" in nueva
    )
    assert "max(12rem,100% / 3)" in nueva
    assert "grid-template-columns:120px 1fr" in nueva  # columnas desiguales: diseño propio
    assert adapta(nueva, FRAG) == nueva


def test_paleta_de_acentos_codigo_y_fondos_de_tokens() -> None:
    assert mapea_colores(".diff{color:#F87171}.ok{color:#34D399}") == (
        ".diff{color:#b0322f}.ok{color:#3d6b1f}"
    )
    assert mapea_colores(".kw{color:#c792ea}.cb{background:#1e1e2e}") == (
        ".kw{color:#6a4aa6}.cb{background:#f1f6ef}"
    )
    # Token oscuro como FONDO -> superficie clara; como color de texto, sin cambio.
    assert mapea_colores(
        "td{background:var(--dark-teal);color:var(--dark-teal)}"
        ".c{background-color:var(--cream-pale)}:root{color-scheme:dark}"
    ) == (
        "td{background:var(--tint);color:var(--dark-teal)}"
        ".c{background-color:var(--tint)}:root{color-scheme:light}"
    )
