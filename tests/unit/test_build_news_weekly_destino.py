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


TODOS = {"Depresión": 39, "Parkinson": 39, "Alzheimer": 39, "Dengue": 39}


def test_la_semana_vigente_exige_el_mismo_corte_en_los_cuatro(tmp_path: Path) -> None:
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
