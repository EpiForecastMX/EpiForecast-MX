"""El generador de novedades debe escribir donde se le dice, y solo ahí.

`bump_static_html` ignoraba la ruta recibida y usaba la constante global del repositorio.
El efecto era doble y silencioso: en el refresh semanal `news.json` iba al staging pero
`index.html` y `novedades.html` acababan en el sitio real, de modo que el sello quedaba
incompleto —esos dos archivos nunca entraban al inventario— y el sitio se modificaba
aunque la corrida no publicara nada. Aplicar ese sello sobre un clon limpio habría dejado
la portada y Novedades en la semana vieja con el resto en la nueva.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
from scripts.build_news_weekly import DASHBOARD, bump_static_html, render_news_banner

PORTADA = """<html><body>
<div class="dateline">Edición de la semana 27, 2026</div>
        <div class="news-banner-row" id="newsBannerRow">
          <a href="novedades.html" class="news-lead">
            <div class="news-lead-meta">
              <span class="news-date">27 de agosto de 2026</span>
              <span class="news-tag news-tag--calass">Internacional</span>
            </div>
            <div class="news-lead-title">EpiForecast-MX se presentó en el CALASS 2026, en Montréal</div>
            <div class="news-lead-sub">La Comunicación 75 ante la ALASS.</div>
          </a>
          <div class="news-mini-list">
            <a href="novedades.html" class="news-mini">
              <span class="news-tag news-tag--datos">Datos</span>
              <span class="news-mini-title">Ya contamos con la semana epidemiológica 27 de 2026</span>
              <span class="news-mini-date">21 de julio de 2026</span>
            </a>
          </div>
        </div>
</body></html>
"""

CALASS = {
    "date": "27 de agosto de 2026",
    "iso": "2026-08-27",
    "type": "calass",
    "tag": "Internacional",
    "featured": True,
    "title": "EpiForecast-MX se presentó en el CALASS 2026, en Montréal",
    "body": ["<p>La <strong>Comunicación 75</strong> ante la ALASS, en Montréal.</p>"],
}
W27 = {
    "date": "21 de julio de 2026",
    "iso": "2026-07-21",
    "type": "datos",
    "tag": "Datos",
    "featured": False,
    "title": "Ya contamos con la semana epidemiológica 27 de 2026",
    "body": ["…"],
}

NOVEDADES = """<html><body>
<div class="dateline">Edición de la semana 27, 2026</div>
</body></html>
"""


def _escribe_news(destino: Path, items: list[dict]) -> None:
    (destino / "news.json").write_text(
        json.dumps({"_generated": items[0]["iso"], "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.fixture
def destino(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES, encoding="utf-8")
    # news.json tal como queda tras upsert_news: la nota semanal primero.
    _escribe_news(tmp_path, [_datos()[1], CALASS, W27])
    return tmp_path


def _datos() -> tuple[dict, dict]:
    data = {"week": 31, "year": 2026}
    item = {
        "title": "Ya contamos con la semana epidemiológica 31 de 2026",
        "iso": "2026-08-18",
        "date": "18 de agosto de 2026",
        "type": "datos",
        "tag": "Datos",
        "body": ["…"],
    }
    return data, item


def test_escribe_en_el_destino_recibido(destino: Path) -> None:
    data, item = _datos()
    bump_static_html(data, item, destino)

    for nombre in ("index.html", "novedades.html"):
        html = (destino / nombre).read_text(encoding="utf-8")
        assert "Edición de la semana 31, 2026" in html
        assert "Edición de la semana 27, 2026" not in html


def test_actualiza_tambien_el_lead_de_la_portada(destino: Path) -> None:
    data, item = _datos()
    bump_static_html(data, item, destino)

    portada = (destino / "index.html").read_text(encoding="utf-8")
    lead = portada[portada.index('class="news-lead"') : portada.index("news-mini-list")]
    assert "semana epidemiológica 31 de 2026" in lead
    assert "semana epidemiológica 27 de 2026" not in lead


def test_no_toca_el_dashboard_canonico(destino: Path) -> None:
    """La prueba que faltaba: el sitio real no puede moverse por una corrida dirigida."""
    canonicos = {
        p: p.read_bytes()
        for nombre in ("index.html", "novedades.html")
        if (p := DASHBOARD / nombre).is_file()
    }
    if not canonicos:
        pytest.skip("el dashboard canónico no está presente en este entorno")

    data, item = _datos()
    bump_static_html(data, item, destino)

    intactos = {p: p.read_bytes() == contenido for p, contenido in canonicos.items()}
    assert all(intactos.values()), (
        f"se modificó el sitio real: {[str(p) for p, ok in intactos.items() if not ok]}"
    )


def test_un_destino_sin_esos_archivos_no_falla(tmp_path: Path) -> None:
    """El generador salta lo que no existe en vez de romper la corrida."""
    data, item = _datos()
    bump_static_html(data, item, tmp_path)

    assert not list(tmp_path.iterdir())


def test_reescribe_el_banner_entero_aunque_el_destacado_fuera_otra_nota(destino: Path) -> None:
    """La forma exacta con la que W33 salió mal a producción (2-sep-2026): el destacado
    estático era el CALASS (a mano). El generador viejo cambiaba fecha y subtítulo sin
    condición y el titular sólo si ya era una nota semanal; el banner quedaba incoherente."""
    data, item = _datos()
    bump_static_html(data, item, destino)
    portada = (destino / "index.html").read_text(encoding="utf-8")
    bloque = portada[portada.index('id="newsBannerRow"') : portada.index("</body>")]
    lead = bloque[: bloque.index("news-mini-list")]
    minis = bloque[bloque.index("news-mini-list") :]
    assert "semana epidemiológica 31 de 2026" in lead
    assert "18 de agosto de 2026" in lead and "news-tag--datos" in lead
    assert "CALASS" not in lead and "news-tag--calass" not in lead
    # las dos notas anteriores bajan a la lista secundaria, en orden
    assert minis.index("CALASS 2026") < minis.index("semana epidemiológica 27 de 2026")
    assert minis.count('class="news-mini"') == 2
    assert "semana epidemiológica 31" not in minis


def test_el_lead_no_semanal_lleva_el_resumen_del_cuerpo(tmp_path: Path) -> None:
    """Cuando el destacado no es la nota semanal, el subtítulo replica `summary()` del JS."""
    html = render_news_banner([CALASS, W27])
    assert "news-tag--calass" in html and "Comunicación 75 ante la ALASS" in html
    assert "<strong>" not in html


def test_falla_en_seco_si_falta_el_bloque_o_news_json(tmp_path: Path) -> None:
    data, item = _datos()
    (tmp_path / "index.html").write_text("<html><body>sin banner</body></html>", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        bump_static_html(data, item, tmp_path)
    _escribe_news(tmp_path, [item, CALASS])
    with pytest.raises(ValueError, match="newsBannerRow"):
        bump_static_html(data, item, tmp_path)
    # y si news.json no lleva la nota semanal primero, tampoco escribe nada
    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    _escribe_news(tmp_path, [CALASS, item])
    with pytest.raises(ValueError, match="upsert_news"):
        bump_static_html(data, item, tmp_path)
    assert "CALASS 2026, en Montréal</div>" in (tmp_path / "index.html").read_text(
        encoding="utf-8"
    )


OBESIDAD_RELEASE = {"nombre": "Obesidad", "origen": [2026, 26], "series": 111}


def _data_w39() -> dict:
    from datetime import date

    return {
        "year": 2026,
        "week": 39,
        "inicio": date(2026, 9, 27),
        "fin": date(2026, 10, 3),
        "corte": "2026-W37",
        "semanas_evaluadas": ["2026-W38", "2026-W39"],
        "graficos": 432,
        "procedencia": {},
    }


def test_la_nota_semanal_no_publica_cifras_de_desempeno() -> None:
    """Ronda W37: ni desviación del acumulado ni SMAPE/MASE en la nota (ni en su subtítulo)."""
    import re

    from scripts.build_news_weekly import SUB_NEUTRAL, build_item

    item = build_item(_data_w39())
    texto = " ".join(item["body"]) + " " + SUB_NEUTRAL
    assert "semana 39" in texto and "(27 de septiembre al 3 de octubre)" in texto
    assert "corte en la semana 37" in texto and "432 gráficos" in texto and "38 y 39" in texto
    assert not re.search(r"(?i)smape|mase|precisi|desv|&#37;|%", texto)


# ── cierre W39: la nota sin Tableau, con entradas explícitas e idempotente ─────────────────────


def _boletin(tmp_path: Path, semanas: dict[str, int]) -> Path:
    import pandas as pd

    filas = [
        {"Anio": 2026, "Semana": s, "Entidad": f"E{e}", "Padecimiento": pad}
        for pad, ultima in semanas.items()
        for s in range(37, ultima + 1)
        for e in range(32)
    ]
    ruta = tmp_path / "boletin.csv"
    pd.DataFrame(filas).to_csv(ruta, index=False)
    return ruta


def _entradas(
    tmp_path: Path, ultima: str = "2026-W39", corte_ag: str = "2026-W37"
) -> tuple[Path, Path, Path]:
    anio, sem = (int(x) for x in ultima.split("-W"))
    seg = tmp_path / "seg.json"
    seg.write_text(
        json.dumps(
            {
                "corte": {"etiqueta": "2026-W37"},
                "ultima_semana_observada": {"etiqueta": ultima, "anio": anio, "semana": sem},
                "semanas_evaluadas": 2,
                "semanas": [{"etiqueta": "2026-W38"}, {"etiqueta": "2026-W39"}],
            }
        ),
        "utf-8",
    )
    cat = tmp_path / "cat.json"
    cat.write_text(
        json.dumps({"gallery_item_count": 432, "production_series_count": 432}), "utf-8"
    )
    ag = tmp_path / "ag.json"
    ag.write_text(json.dumps({"corte": corte_ag}), "utf-8")
    return seg, cat, ag


def _todos() -> dict[str, int]:
    from epiforecast import registry

    return {pad: 39 for pad in registry.published_members()}


TODOS = _todos()


def test_la_semana_vigente_exige_el_mismo_corte_en_todos(tmp_path: Path) -> None:
    from scripts.build_news_weekly import compute_data, semana_vigente

    assert semana_vigente(_boletin(tmp_path, TODOS)) == (2026, 39)
    with pytest.raises(ValueError, match="corte desigual"):
        semana_vigente(_boletin(tmp_path, {**TODOS, "Dengue": 38}))
    seg, cat, ag = _entradas(tmp_path, ultima="2026-W38")
    with pytest.raises(ValueError, match="el seguimiento termina en 2026-W38"):
        compute_data(_boletin(tmp_path, TODOS), seg, cat, ag)
    seg, cat, ag = _entradas(tmp_path, corte_ag="2026-W33")
    with pytest.raises(ValueError, match="agregado estatal"):
        compute_data(_boletin(tmp_path, TODOS), seg, cat, ag)


def test_reaplicar_la_semana_no_anade_ni_reescribe_y_no_lee_tableau(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    import builtins

    from scripts import build_news_weekly as g

    abrir = builtins.open

    def vigila(f, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        assert "tableau" not in str(f), f"lee {f}"
        return abrir(f, *a, **k)

    monkeypatch.setattr(builtins, "open", vigila)
    # El release sellado vive en DVC (ausente en CI): la nota lo lee de su manifiesto.
    monkeypatch.setattr(g, "releases_publicados", lambda *_a, **_k: [OBESIDAD_RELEASE])
    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES, encoding="utf-8")
    _escribe_news(tmp_path, [CALASS, W27])
    seg, cat, ag = _entradas(tmp_path)
    args = [
        "--dashboard",
        str(tmp_path),
        "--boletin",
        str(_boletin(tmp_path, TODOS)),
        "--seguimiento",
        str(seg),
        "--catalogo",
        str(cat),
        "--agregado",
        str(ag),
        "--fecha",
        "2026-10-14",
    ]
    assert g.main(args) == 0
    primero = (tmp_path / "news.json").read_bytes(), (tmp_path / "index.html").read_bytes()
    assert g.main([*args[:-1], "2026-10-21"]) == 0  # otro día, misma semana y mismas entradas
    assert (
        (tmp_path / "news.json").read_bytes(),
        (tmp_path / "index.html").read_bytes(),
    ) == primero
    items = json.loads(primero[0])["items"]
    assert [it["title"] for it in items].count(
        "Ya contamos con la semana epidemiológica 39 de 2026"
    ) == 1
    assert items[0]["iso"] == "2026-10-14" and len(items) == 3
    assert "Edición de la semana 39, 2026" in primero[1].decode()


def test_obesidad_publicada_entra_en_la_paridad_y_en_la_nota(tmp_path: Path) -> None:
    """C7.7: con Obesidad publicada son cinco; si se queda atrás, la semana no cierra.

    El estado publicado se FIJA (registry_c77): la prueba no depende de que el registry vivo siga
    así, y sigue verde tras el rollback de la guía."""
    from scripts.build_news_weekly import SUB_NEUTRAL, build_item, publicados, semana_vigente

    from tests.unit.registry_pre_c77 import registry_c77

    with registry_c77():
        todos = _todos()
        assert "Obesidad" in publicados() and len(publicados()) == 5
        with pytest.raises(ValueError, match="corte desigual"):
            semana_vigente(_boletin(tmp_path, {**todos, "Obesidad": 38}))
        sin = {k: v for k, v in todos.items() if k != "Obesidad"}
        with pytest.raises(ValueError, match="Obesidad sin ninguna semana completa"):
            semana_vigente(_boletin(tmp_path, sin))
        body = " ".join(build_item(_data_w39())["body"])
    assert "en los cinco padecimientos" in body and "cuatro padecimientos" not in body
    assert "cuatro" not in SUB_NEUTRAL


def test_la_nota_distingue_el_carril_semanal_del_release() -> None:
    """Auditoría C7.7: «cinco padecimientos» no puede ir seguido de un corte y una galería que
    sólo describen a los cuatro del carril semanal."""
    from scripts.build_news_weekly import build_item

    body = " ".join(build_item({**_data_w39(), "releases": [OBESIDAD_RELEASE]})["body"])
    assert "Los pronósticos de Depresión, Parkinson, Alzheimer y Dengue" in body
    assert "corte en la semana 37" in body and "sus 432 gráficos" in body
    assert "Obesidad conserva su pronóstico, con datos hasta la semana 26 de 2026" in body
    assert "suma 111 series a la galería" in body


def test_los_releases_se_leen_de_su_manifiesto_y_fallan_cerrados(tmp_path: Path) -> None:
    import json

    from scripts.build_news_weekly import releases_publicados

    from epiforecast.publication.status import load_declared_status
    from tests.unit.registry_pre_c77 import registry_c77

    rid = load_declared_status("obesidad").release_id
    with registry_c77():
        with pytest.raises(FileNotFoundError):
            releases_publicados(tmp_path)
        raiz = tmp_path / "obesidad" / rid
        raiz.mkdir(parents=True)
        (raiz / "release_manifest.json").write_text(
            json.dumps({"calendar": {"origin": [2026, 26]}, "counts": {"products": 111}}),
            encoding="utf-8",
        )
        assert releases_publicados(tmp_path) == [OBESIDAD_RELEASE]


# --- Rediseño (piloto 2026-11): anclas por nota y portada en formato multilínea ------------------
# Vectores compartidos con el frontend (EpiForecast-IMSS-Dashboard tests/home.test.mjs): la portada
# enlaza a `novedades.html#<ancla>` y novedades.html pone ese mismo id a cada nota.
VECTORES_ANCLA = [
    (
        {
            "iso": "2026-11-10",
            "title": "Las neumonías y bronconeumonías se publican con el control estacional",
        },
        "nota-2026-11-10-las-neumonias-y-bronconeumonias-se-publican-con",
    ),
    (
        {
            "iso": "2026-09-03",
            "title": "EpiForecast-MX va al Congreso Mundial de Psiquiatría, en Estocolmo",
        },
        "nota-2026-09-03-epiforecast-mx-va-al-congreso-mundial-de-psiquia",
    ),
    (
        {"iso": "2026-05-21", "title": "¿Qué es «EPI»? Ñandú — 100 % año"},
        "nota-2026-05-21-que-es-epi-nandu-100-ano",
    ),
    ({"iso": "x", "title": "***"}, "nota-sin-fecha-sin-titulo"),
]


def test_el_ancla_de_cada_nota_es_la_misma_que_calcula_el_frontend() -> None:
    from scripts.build_news_weekly import anclas, nota_ancla

    for it, esperado in VECTORES_ANCLA:
        assert nota_ancla(it) == esperado
    repetidas = [VECTORES_ANCLA[0][0], VECTORES_ANCLA[0][0]]
    assert anclas(repetidas) == [VECTORES_ANCLA[0][1], VECTORES_ANCLA[0][1] + "-2"]


def test_el_banner_enlaza_cada_nota_a_su_ancla() -> None:
    from scripts.build_news_weekly import nota_ancla

    html = render_news_banner([CALASS, W27])
    assert f'href="novedades.html#{nota_ancla(CALASS)}" class="news-lead"' in html
    assert f'href="novedades.html#{nota_ancla(W27)}" class="news-mini"' in html
    assert 'href="novedades.html" ' not in html


PORTADA_REDISENO = """<!DOCTYPE html>
<html lang="es"><body class="home">
<!-- site:header:start -->
<header class="site-header" id="nav"></header>
<!-- site:header:end -->
<main id="main">
<section class="home-hero" id="hero"><p class="edition"><span class="dot"></span>Edición de la semana 27, 2026</p></section>
<!-- home:news:start · el bloque #newsBannerRow lo reescribe build_news_weekly.py -->
<section class="home-news" id="novedades" aria-labelledby="news-title">
  <div class="wrap">
      <div class="news-banner">
        <div class="news-banner-head">
          <div><p class="eyebrow">Noticias</p><h2 id="news-title">Lo último en EpiForecast</h2></div>
        </div>
        <div class="news-banner-row" id="newsBannerRow">
          <a href="novedades.html#nota-2026-08-27-x" class="news-lead">
            <div class="news-lead-title">EpiForecast-MX se presentó en el CALASS 2026, en Montréal</div>
          </a>
          <div class="news-mini-list">
          </div>
        </div>
      </div>
  </div>
</section>
<!-- home:news:end -->
<section class="home-band home-congresos" id="congresos"><div class="wrap"></div></section>
</main>
</body></html>
"""


@pytest.mark.parametrize(
    "portada", [PORTADA, PORTADA_REDISENO], ids=["formato-anterior", "rediseno"]
)
def test_el_generador_acepta_la_portada_anterior_y_la_del_rediseno(
    tmp_path: Path, portada: str
) -> None:
    """Migración pareada: el mismo generador escribe ambas portadas, y sólo dentro del bloque."""
    (tmp_path / "index.html").write_text(portada, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES, encoding="utf-8")
    data, item = _datos()
    _escribe_news(tmp_path, [item, CALASS, W27])
    bump_static_html(data, item, tmp_path)
    nueva = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Edición de la semana 31, 2026" in nueva
    bloque = nueva[nueva.index('id="newsBannerRow"') :]
    assert "semana epidemiológica 31 de 2026" in bloque[: bloque.index("news-mini-list")]
    # Fuera del bloque y del dateline, nada cambia.
    fuera = lambda h: re.sub(  # noqa: E731
        r'(<div class="news-banner-row" id="newsBannerRow">).*?(\n {8}</div>)',
        r"\1\2",
        h,
        flags=re.S,
    ).replace("semana 31, 2026", "semana 27, 2026")
    assert fuera(nueva) == fuera(portada)
    # Idempotente: reaplicar no cambia nada.
    bump_static_html(data, item, tmp_path)
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == nueva


# --- Archivo estático de Noticias (hito 3) -------------------------------------------------------

NOVEDADES_REDISENO = """<html><body>
<div class="dateline">Edición de la semana 27, 2026</div>
<div class="arch-list" id="newsGrid"><!-- noticias:archivo:start --><!-- noticias:archivo:end --></div>
</body></html>
"""


def test_el_archivo_estatico_lleva_cada_nota_con_su_ancla_en_orden() -> None:
    from scripts.build_news_weekly import anclas, render_archivo_noticias

    items = [CALASS, W27, dict(W27)]  # la repetida lleva sufijo -2, como en el frontend
    html = render_archivo_noticias(items)
    ids = re.findall(r'<article class="arch-item[^"]*" id="([^"]+)" tabindex="-1">', html)
    assert ids == anclas(items)
    assert ids[2] == ids[1] + "-2"
    # Mismo marcado que `ih` de novedades.html: la primera siempre destacada.
    assert html.count("arch-item--featured") >= 1
    assert html.lstrip().startswith('<article class="arch-item arch-item--featured"')
    for it in items:
        assert (
            f'<h2 class="arch-title"><a href="{(it.get("link") or {}).get("href") or "#"}">{it["title"]}</a></h2>'
            in html
        )


def test_bump_escribe_el_archivo_y_es_idempotente(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES_REDISENO, encoding="utf-8")
    data, item = _datos()
    _escribe_news(tmp_path, [item, CALASS, W27])
    bump_static_html(data, item, tmp_path)
    nov = (tmp_path / "novedades.html").read_text(encoding="utf-8")
    assert nov.count('<article class="arch-item') == 3
    assert "Edición de la semana 31, 2026" in nov
    bump_static_html(data, item, tmp_path)
    assert (tmp_path / "novedades.html").read_text(encoding="utf-8") == nov


def test_la_plantilla_sin_bloque_de_archivo_no_cambia(destino: Path) -> None:
    from scripts.build_news_weekly import reescribe_archivo

    assert reescribe_archivo(NOVEDADES, [CALASS]) == NOVEDADES
    with pytest.raises(ValueError):
        reescribe_archivo(NOVEDADES_REDISENO + NOVEDADES_REDISENO, [CALASS])


def test_solo_estaticos_reescribe_sin_red_y_reporta_sin_cambios(tmp_path: Path) -> None:
    from scripts.build_news_weekly import main

    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES_REDISENO, encoding="utf-8")
    _escribe_news(tmp_path, [CALASS, W27])
    news_antes = (tmp_path / "news.json").read_bytes()
    assert main(["--solo-estaticos", "--dashboard", str(tmp_path)]) == 0
    nov = (tmp_path / "novedades.html").read_text(encoding="utf-8")
    assert nov.count('<article class="arch-item') == 2
    assert (tmp_path / "news.json").read_bytes() == news_antes
    antes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert main(["--solo-estaticos", "--dashboard", str(tmp_path)]) == 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == antes
